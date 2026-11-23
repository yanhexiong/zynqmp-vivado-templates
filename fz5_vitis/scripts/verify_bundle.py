"""Validate exported XSA geometry/IP presence before building software."""
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile


def verify(folder):
    folder = Path(folder)
    cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    expected = cfg.pop("CONFIG_ID")
    actual = hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if expected != actual:
        raise ValueError("config.json content/hash mismatch")
    cfg["CONFIG_ID"] = expected
    for name in ("config.tcl", "fz5_config.h", "config_id.txt"):
        if expected not in (folder / name).read_text(encoding="utf-8"):
            raise ValueError(f"stale {name}")
    with zipfile.ZipFile(folder / "fz5_system.xsa") as z:
        names = z.namelist()
        hwh = ET.fromstring(z.read(next(n for n in names if n.endswith(".hwh"))))
        meta = json.loads(z.read("xsa.json"))
        assert meta["devices"][0]["part"]["name"] == cfg["PART"], "XSA device differs from configuration"
        ps = hwh.find('.//MODULE[@INSTANCE="ps"]')
        p = {p.attrib["NAME"]: p.attrib.get("VALUE", "") for p in ps.findall("PARAMETERS/PARAMETER")}
        rows = "17" if cfg["BOARD_FZ5D"] else "16"
        assert p["PSU__DDRC__ROW_ADDR_COUNT"] == rows, "XSA DDR geometry differs from configuration"
        assert p["PSU__DDRC__BUS_WIDTH"] == "64 Bit"
        assert abs(float(p["PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ"]) - cfg["PL_CLOCK_MHZ"]) < 1, "PL clock differs from configuration"
        for symbol, block in [("PL_GPIO", "gpio"), ("PL_DMA", "dma"), ("PL_BRAM", "bram_ctrl"), ("PL_RS232", "rs232")]:
            assert bool(hwh.find(f'.//MODULE[@INSTANCE="{block}"]') is not None) == bool(cfg[symbol]), f"XSA {block} presence mismatch"
        if any(cfg[symbol] for symbol in ("PL_GPIO", "PL_DMA", "PL_BRAM", "PL_RS232")):
            reset = hwh.find('.//MODULE[@INSTANCE="reset"]')
            if (reset is None or
                    reset.find('PARAMETERS/PARAMETER[@NAME="C_EXT_RESET_HIGH"][@VALUE="0"]') is None or
                    reset.find('PARAMETERS/PARAMETER[@NAME="C_AUX_RESET_HIGH"][@VALUE="1"]') is None):
                raise ValueError("XSA has the wrong PL reset polarity. Rebuild the bitstream from the updated template.")
        for symbol, prefix in [("PS_UART1", "UART1"), ("PS_I2C1", "I2C1"), ("PS_GEM3", "ENET3"), ("PS_CAN1", "CAN1"), ("PS_EMMC", "SD0"), ("PS_SD", "SD1"), ("PS_QSPI", "QSPI"), ("PS_USB0", "USB0"), ("PS_DP", "DISPLAYPORT")]:
            assert int(p[f"PSU__{prefix}__PERIPHERAL__ENABLE"]) == int(cfg[symbol]), f"XSA {prefix} state mismatch"
        bit = next((n for n in names if n.endswith(".bit")), None)
        if not bit:
            raise ValueError("XSA has no bitstream; run Vivado bitstream first")
        assert z.read(bit) == (folder / "fz5_system.bit").read_bytes(), "external bitstream differs from XSA"
    digest = hashlib.sha256((folder / "fz5_system.xsa").read_bytes()).hexdigest()
    print(f"Bundle verified: config={expected[:12]} XSA-SHA256={digest}")
    return cfg, digest


if __name__ == "__main__":
    verify(sys.argv[1])
