"""Attach the routed BIT to Vivado's fixed-shell XSA for the in-context flow.

Vivado 2023.1 -include_bit searches a managed implementation run. This flow
calls synth/place/route directly, so package its existing XSA and BIT instead.
The three BIT descriptors follow the format of the supplied 2023.1 XSA.
HWH, PS init files, BDA and all other tool-generated content are kept verbatim.
"""
import argparse
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import zipfile


def package(source, bit, target):
    source, bit, target = Path(source), Path(bit), Path(target)
    if bit.stat().st_size < 1024:
        raise ValueError("Missing/truncated bitstream")
    with zipfile.ZipFile(source) as z:
        data = {n: z.read(n) for n in z.namelist()}
    if any(n.endswith(".bit") for n in data):
        raise ValueError("Input XSA must be the Vivado pre-synthesis export")
    sysdef = ET.fromstring(data.pop("hwdef.xml") if "hwdef.xml" in data else data["sysdef.xml"])
    mode = sysdef.find("MODE")
    if mode is not None:
        mode.set("Name", "Post-Synthesis")
    ET.SubElement(sysdef, "File", Type="BIT", Name=bit.name, src_db="fz5_in_context")
    data["sysdef.xml"] = ET.tostring(sysdef, encoding="utf-8", xml_declaration=True)
    xml = ET.fromstring(data["xsa.xml"])
    dsa = xml.find("DSA")
    files = dsa.find("Files")
    if files is None:
        files = ET.SubElement(dsa, "Files")
    ET.SubElement(files, "File", Type="FULL_BIT", Name=bit.name)
    data["xsa.xml"] = ET.tostring(xml, encoding="utf-8", xml_declaration=True)
    meta = json.loads(data["xsa.json"])
    meta["files"] = meta.get("files", []) + [{"name": bit.name, "type": "FULL_BIT"}]
    data["xsa.json"] = (json.dumps(meta, indent=4) + "\n").encode()
    data[bit.name] = bit.read_bytes()
    temp = target.with_suffix(".xsa.tmp")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for n, content in data.items():
            z.writestr(n, content)
    with zipfile.ZipFile(temp) as z:
        if z.testzip() is not None or z.read(bit.name) != bit.read_bytes():
            raise ValueError("XSA verification failed")
    temp.replace(target)
    print("FZ5_XSA_OK:", target)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("bit", type=Path)
    p.add_argument("target", type=Path)
    p.add_argument("--config-dir", type=Path)
    p.add_argument("--publish", type=Path)
    a = p.parse_args()
    package(a.source, a.bit, a.target)
    if a.publish:
        if not a.config_dir:
            p.error("--publish requires --config-dir")
        a.publish.mkdir(parents=True, exist_ok=True)
        for n in ["config.json", "config.tcl", "fz5_config.h", "fz5-memory.dtsi"]:
            shutil.copy2(a.config_dir / n, a.publish / n)
        shutil.copy2(a.target, a.publish / "fz5_system.xsa")
        shutil.copy2(a.bit, a.publish / "fz5_system.bit")
        cfg = json.loads((a.config_dir / "config.json").read_text(encoding="utf-8"))
        (a.publish / "config_id.txt").write_text(cfg["CONFIG_ID"] + "\n", encoding="utf-8")
        print("FZ5_EXPORT_OK:", a.publish)
