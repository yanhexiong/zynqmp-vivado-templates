"""Run on the target Linux image built from the matching XSA/device tree.

Usage: python3 linux_probe.py --config config.json [--peer 192.168.1.2]
Only reads sysfs/device tree, and optionally sends ping packets. No shell used.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time


def read(path):
    try:
        return Path(path).read_text().strip().strip("\0")
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--peer")
    ap.add_argument("--netdev", default="eth0")
    ap.add_argument("--output", type=Path, default=Path("linux-result.json"))
    a = ap.parse_args()
    cfg = json.loads(a.config.read_text())
    loaded = read("/proc/device-tree/fz5-config-id")
    if loaded != cfg["CONFIG_ID"]:
        ap.error("device-tree config ID mismatch/missing; include matching fz5-memory.dtsi and rebuild Linux DT")
    rows = []

    def report(name, status, detail):
        rows.append(dict(test=name, status=status, detail=detail))
        print(f"[{status}] {name}: {detail}")

    if cfg["PL_POOL_SIZE"]:
        pools = list(Path("/proc/device-tree/reserved-memory").glob("pl-pool@*"))
        ok = any((p / "no-map").exists() and (p / "reg").read_bytes() == cfg["PL_POOL_BASE"].to_bytes(8, "big") + cfg["PL_POOL_SIZE"].to_bytes(8, "big") for p in pools)
        report("PL DDR reservation", "PASS" if ok else "FAIL", "checks reg address/size and no-map in loaded DT")

    if cfg["PS_GEM3"]:
        dev = Path("/sys/class/net") / a.netdev
        correct = "ff0e0000" in str((dev / "device").resolve())
        carrier = read(dev / "carrier") == "1"
        report("GEM3 Linux link", "PASS" if correct and carrier else "FAIL", f"{a.netdev} carrier={carrier} speed={read(dev / 'speed')} Mbps")
        if a.peer:
            r = subprocess.run(["ping", "-I", a.netdev, "-c", "4", "-W", "2", a.peer], capture_output=True, text=True, timeout=15)
            report("GEM3 peer ICMP", "PASS" if r.returncode == 0 else "FAIL", r.stdout.strip())
        else:
            report("GEM3 peer traffic", "MANUAL", "supply --peer for ping; use iperf separately for throughput")

    if cfg["PS_USB0"]:
        devices = []
        for p in Path("/sys/bus/usb/devices").glob("*"):
            vid = read(p / "idVendor")
            if vid:
                devices.append(dict(name=p.name, vid=vid, pid=read(p / "idProduct"), speed=read(p / "speed"), device_class=read(p / "bDeviceClass")))
        external = [d for d in devices if d["device_class"] != "09"]
        report("USB host enumeration", "PASS" if external else "FAIL", json.dumps(devices))
        if cfg["PS_USB3"]:
            fast = [d for d in external if float(d["speed"] or "0") >= 5000]
            report("USB3 external device", "PASS" if fast else "FAIL", "requires a SuperSpeed device; repeat on each physical port")

    if cfg["PS_DP"]:
        connectors = [p for p in Path("/sys/class/drm").glob("*-DP-*") if read(p / "status") == "connected"]
        edid_ok = any((p / "edid").exists() and len((p / "edid").read_bytes()) >= 128 for p in connectors)
        report("DisplayPort EDID", "PASS" if edid_ok else "FAIL", ", ".join(p.name for p in connectors))
        report("DisplayPort picture", "MANUAL", "confirm real test pattern on monitor")

    if cfg["PS_RTC"]:
        before = read("/sys/class/rtc/rtc0/since_epoch")
        time.sleep(1.2)
        after = read("/sys/class/rtc/rtc0/since_epoch")
        ok = before.isdigit() and after.isdigit() and int(after) > int(before)
        report("RTC ticking", "PASS" if ok else "FAIL", f"{before} -> {after}")
        report("RTC battery retention", "MANUAL", "set time, remove main power, reboot and compare")

    a.output.write_text(json.dumps(dict(config_id=loaded, results=rows), indent=2) + "\n")
    return int(any(r["status"] == "FAIL" for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
