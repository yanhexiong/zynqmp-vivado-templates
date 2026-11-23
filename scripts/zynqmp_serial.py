"""Shared cross-platform UART diagnostic capture and optional JTAG launch."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from typing import Callable

from zynqmp_host import BOARD_SPECS, REPO_ROOT, run_jtag_download

SERIAL_PROFILES = {
    "axu4ev": {
        "board_name": "AXU4EV-F",
        "end_prefix": "AXU4EV_DIAG_END",
        "echo_flag": "PL_UART",
        "echo_pass_marker": "[PASS] PL UART CP2102 echo:",
        "echo_help": "a different USB virtual COM connected to the PL UART",
        "echo_fail_msg": "PL UART echo did not pass. Check the PL port and DIAG_EXTERNAL_LOOPBACK in src/test_options.h.",
        "default_echo_delay_ms": 0.0,
    },
    "fz5": {
        "board_name": None,  # accepts FZ5D or FZ5C
        "end_prefix": "FZ5_DIAG_END",
        "echo_flag": "PS_UART1",
        "echo_pass_marker": "[PASS] UART1 RS485 echo:",
        "echo_help": "a different USB serial port connected to RS485/UART1 for delayed echo",
        "echo_fail_msg": "RS485 echo did not pass. Check the peer port, wiring, and DIAG_EXTERNAL_LOOPBACK in src/test_options.h.",
        "default_echo_delay_ms": 15.0,
    },
}


def build_serial_parser(board: str, description: str) -> argparse.ArgumentParser:
    """Create a uniform cross-platform serial/JTAG parser for a board."""
    spec = BOARD_SPECS[board]
    prof = SERIAL_PROFILES[board]
    default_hw = REPO_ROOT / spec["template_dir"] / "export"
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--console", required=True, help="Console serial port (e.g. COM4 or /dev/ttyUSB0)")
    p.add_argument("--pl-echo", help=prof["echo_help"])
    p.add_argument(
        "--echo-delay-ms",
        type=float,
        default=prof["default_echo_delay_ms"],
        help="Delay in milliseconds before echoing received bytes (useful for RS485 turnaround)",
    )
    p.add_argument("--hardware", type=Path, default=default_hw)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--output", type=Path, help="Output report JSON path (also writes .uart.log alongside)")
    p.add_argument("--jtag", action="store_true", help="Download FSBL/PMUFW/bitstream/ELF over JTAG after opening UART")
    p.add_argument("--workspace", type=Path, help="Custom Vitis workspace path for --jtag")
    p.add_argument("--server", default="tcp:127.0.0.1:3121", help="hw_server URL for --jtag")
    p.add_argument("--cable", default="*", help="JTAG cable filter pattern for --jtag")
    p.add_argument("--vitis-dir", type=Path, help="Explicit Vitis installation directory for --jtag")
    p.add_argument("--tool-version", help="Vitis version to select for --jtag")
    return p


def run_serial_capture(
    board: str,
    argv: list[str] | None,
    *,
    serial_factory: Callable[..., object],
    description: str,
) -> int:
    """Run UART capture (and optional JTAG boot) and write JSON + uart.log reports."""
    prof = SERIAL_PROFILES[board]
    spec = BOARD_SPECS[board]
    parser = build_serial_parser(board, description)
    args = parser.parse_args(argv)
    if args.pl_echo and args.pl_echo == args.console:
        parser.error("--pl-echo must be different from the PS console port")

    hw_dir = Path(args.hardware)
    cfg = json.loads((hw_dir / "config.json").read_text(encoding="utf-8-sig"))
    expected_board = prof["board_name"]
    if expected_board and cfg["BOARD_NAME"] != expected_board:
        parser.error(f"Not an {expected_board} configuration")
    if not expected_board and not str(cfg.get("BOARD_NAME", "")).startswith("FZ5"):
        parser.error("Not an FZ5 configuration")
    if args.pl_echo and not cfg.get(prof["echo_flag"]):
        parser.error(f"Enable {prof['echo_flag']} in the hardware configuration before testing its echo")

    if args.output:
        output_path = Path(args.output)
        log_path = output_path.with_suffix(".uart.log")
    else:
        build_dir = REPO_ROOT / spec["vitis_dir"] / "build" / cfg["CONFIG_ID"][:12]
        build_dir.mkdir(parents=True, exist_ok=True)
        output_path = build_dir / "hardware-result.json"
        log_path = build_dir / "uart.log"

    text = ""
    peer = None
    pattern = re.compile(rf"{prof['end_prefix']} config=([0-9a-f]{{64}}) pass=(\d+) fail=(\d+) skip=(\d+) manual=(\d+)")
    try:
        if args.pl_echo:
            peer = serial_factory(args.pl_echo, 115200, timeout=0, write_timeout=1)
        with serial_factory(args.console, 115200, timeout=0.1) as console:
            if args.jtag:
                run_jtag_download(
                    board,
                    hardware=hw_dir,
                    workspace=args.workspace,
                    server=args.server,
                    cable=args.cable,
                    vitis_dir=args.vitis_dir,
                    tool_version=args.tool_version,
                )
            else:
                print("UART capture ready. Boot/reset the diagnostic image now.", flush=True)
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                if peer:
                    data = peer.read(64)
                    if data:
                        if args.echo_delay_ms > 0:
                            time.sleep(args.echo_delay_ms / 1000.0)
                        peer.write(data)
                chunk = console.read(4096).decode("utf-8", errors="replace")
                if chunk:
                    text += chunk
                    print(chunk, end="", flush=True)
                match = pattern.search(text)
                if match:
                    counts = dict(zip(("pass", "fail", "skip", "manual"), map(int, match.groups()[1:])))
                    report = {
                        "config_id": match[1],
                        "expected_config_id": cfg["CONFIG_ID"],
                        "port": args.console,
                        **counts,
                        "config_matches": match[1] == cfg["CONFIG_ID"],
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                    }
                    echo_failed = False
                    if args.pl_echo:
                        report["pl_echo_verified"] = prof["echo_pass_marker"] in text
                        echo_failed = not report["pl_echo_verified"]
                        if echo_failed:
                            print(prof["echo_fail_msg"], file=sys.stderr)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                    print(f"\nReport: {output_path}")
                    return int(not report["config_matches"] or report["fail"] > 0 or echo_failed)
            raise TimeoutError(f"No {prof['end_prefix']}; check boot mode, console, DDR training and power")
    finally:
        if peer:
            peer.close()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(text, encoding="utf-8")
