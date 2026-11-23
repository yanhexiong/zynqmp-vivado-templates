"""Capture FZ5 diagnostics over UART; optionally launch JTAG or echo RS485/UART1.

Run with: uv run --with pyserial python scripts/serial_test.py --console COM7
Linux ports such as /dev/ttyUSB0 are supported. Pass --jtag to download over JTAG first.
"""
from __future__ import annotations

from pathlib import Path
import sys

try:
    import serial
except ModuleNotFoundError as exc:
    print("pyserial is required. Run with: uv run --with pyserial python scripts/serial_test.py ...", file=sys.stderr)
    raise SystemExit(2) from exc

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from zynqmp_serial import run_serial_capture


def main(argv: list[str] | None = None) -> int:
    return run_serial_capture("fz5", argv, serial_factory=serial.Serial, description=__doc__ or "")


if __name__ == "__main__":
    raise SystemExit(main())
