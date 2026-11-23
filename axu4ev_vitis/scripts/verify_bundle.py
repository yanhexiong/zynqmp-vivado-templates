"""Validate the AXU4EV-F hardware/configuration handoff before software builds."""
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(folder):
    folder = Path(folder)
    cfg = json.loads((folder / "config.json").read_text(encoding="utf-8-sig"))
    content = {k: v for k, v in cfg.items() if k != "CONFIG_ID"}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(cfg["CONFIG_ID"] == digest, "config.json content/hash mismatch")
    require(cfg["BOARD_NAME"] == "AXU4EV-F", "Not an AXU4EV-F hardware bundle")
    require(cfg["PART"] == "xczu4ev-sfvc784-2-i", "Wrong FPGA device")
    require(cfg["DDR_TOTAL_BYTES"] == 4 * 2**30 and cfg["DDR_HIGH_BASE"] == 0x800000000
            and cfg["DDR_HIGH_SIZE"] == 2 * 2**30, "Wrong physical DDR geometry")
    if cfg["PL_POOL_SIZE"]:
        require(cfg["PL_POOL_BASE"] >= cfg["DDR_HIGH_BASE"] and
                cfg["PL_POOL_BASE"] + cfg["PL_POOL_SIZE"] <= cfg["DDR_HIGH_BASE"] + cfg["DDR_HIGH_SIZE"],
                "PL pool lies outside populated physical DDR")
    for name in ("config.tcl", "axu4ev_config.h", "config_id.txt"):
        require(digest in (folder / name).read_text(encoding="utf-8"), f"Stale {name}")
    with zipfile.ZipFile(folder / "axu4ev_system.xsa") as z:
        # Native exports also carry separate HWHs for hierarchical interconnects.
        # Select the unique system handoff containing the configured PS.
        handoffs = [ET.fromstring(z.read(n)) for n in z.namelist() if n.endswith(".hwh")]
        systems = [h for h in handoffs if h.find('.//MODULE[@INSTANCE="ps"]') is not None]
        require(len(systems) == 1, "Expected one system handoff containing the PS")
        hwh = systems[0]
        metadata = json.loads(z.read("xsa.json"))
        require(metadata["devices"][0]["part"]["name"] == cfg["PART"], "XSA part differs from configuration")
        ps = hwh.find('.//MODULE[@INSTANCE="ps"]')
        require(ps is not None, "XSA has no PS instance")
        p = {r.attrib["NAME"]: r.attrib.get("VALUE", "") for r in ps.findall("PARAMETERS/PARAMETER")}
        require(p["PSU__DDRC__ROW_ADDR_COUNT"] == "16" and p["PSU__DDRC__BUS_WIDTH"] == "64 Bit",
                "XSA DDR geometry differs from AXU4EV-F")
        require(abs(float(p["PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ"]) - cfg["PL_CLOCK_MHZ"]) < 1,
                "XSA PL clock differs from configuration")
        for symbol, instance in (("PL_GPIO", "gpio"), ("PL_BRAM", "bram_ctrl"),
                                 ("PL_DMA", "dma"), ("PL_UART", "uart")):
            require((hwh.find(f'.//MODULE[@INSTANCE="{instance}"]') is not None) == bool(cfg[symbol]),
                    f"XSA {instance} presence mismatch")
        if any(cfg[symbol] for symbol in ("PL_GPIO", "PL_BRAM", "PL_DMA", "PL_UART")):
            reset = hwh.find('.//MODULE[@INSTANCE="reset"]')
            require(reset is not None
                    and reset.find('PARAMETERS/PARAMETER[@NAME="C_EXT_RESET_HIGH"][@VALUE="0"]') is not None
                    and reset.find('PARAMETERS/PARAMETER[@NAME="C_AUX_RESET_HIGH"][@VALUE="1"]') is not None,
                    "XSA has the wrong PL reset polarity. Rebuild the bitstream from the updated template.")
        for symbol, prefix in (("PS_UART0", "UART0"), ("PS_I2C0", "I2C0"), ("PS_GEM3", "ENET3"),
                               ("PS_EMMC", "SD0"), ("PS_SD", "SD1"), ("PS_QSPI", "QSPI"),
                               ("PS_USB0", "USB0"), ("PS_DP", "DISPLAYPORT")):
            require(int(p[f"PSU__{prefix}__PERIPHERAL__ENABLE"]) == int(cfg[symbol]),
                    f"XSA {prefix} state mismatch")
        bit_files = [n for n in z.namelist() if n.endswith(".bit")]
        require(len(bit_files) == 1, "Build the bitstream before building software")
        require(z.read(bit_files[0]) == (folder / "axu4ev_system.bit").read_bytes(), "XSA/external bitstream mismatch")
    xsa_sha = hashlib.sha256((folder / "axu4ev_system.xsa").read_bytes()).hexdigest()
    print(f"Bundle verified: config={digest[:12]} XSA-SHA256={xsa_sha}")
    return cfg, xsa_sha


if __name__ == "__main__":
    verify(sys.argv[1])
