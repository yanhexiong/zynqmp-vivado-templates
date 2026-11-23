"""Unified cross-platform CLI for FZ5 and AXU4EV-F Vivado/Vitis workflows."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from zynqmp_host import (
    BOARD_SPECS,
    REPO_ROOT,
    discover_toolchains,
    format_toolchains,
    run_jtag_download,
    run_matrix_check,
    run_template_config,
    run_vitis_action,
    run_vivado_action,
)


def _add_toolchain_args(parser: argparse.ArgumentParser, *, vivado: bool = False, vitis: bool = False) -> None:
    parser.add_argument("--tool-version", help="Select installed Vivado/Vitis version (e.g. 2023.1, 2024.1)")
    if vivado:
        parser.add_argument("--vivado-dir", type=Path, help="Explicit Vivado installation directory")
        parser.add_argument("--strict-version", action="store_true", help="Require exact Vivado 2023.1")
    if vitis:
        parser.add_argument("--vitis-dir", type=Path, help="Explicit Vitis installation directory")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zynqmp", description="Cross-platform Vivado/Vitis workflow runner.")
    sub = p.add_subparsers(dest="command", required=True)

    tc = sub.add_parser("toolchains", help="List detected Vivado and Vitis installations")
    tc.add_argument("--product", choices=["Vivado", "Vitis"], help="Filter by tool product")

    cfg = sub.add_parser("config", help="Run the Kconfig editor/CLI for a board")
    cfg.add_argument("board", choices=sorted(BOARD_SPECS))
    cfg.add_argument("args", nargs=argparse.REMAINDER, help="Arguments forwarded to <board>-config")

    viv = sub.add_parser("vivado", help="Build Vivado project or bitstream in batch mode")
    viv.add_argument("board", choices=sorted(BOARD_SPECS))
    viv.add_argument("action", choices=["project", "bitstream"])
    viv.add_argument("--config-dir", type=Path, help="Custom generated config directory")
    _add_toolchain_args(viv, vivado=True)

    mat = sub.add_parser("matrix", help="Check multiple defconfig profiles in Vivado")
    mat.add_argument("board", choices=sorted(BOARD_SPECS))
    mat.add_argument("--profiles", nargs="+", help="Profiles to validate")
    _add_toolchain_args(mat, vivado=True)

    vit = sub.add_parser("vitis", help="Build Vitis workspace/ELF or package BOOT.BIN")
    vit.add_argument("board", choices=sorted(BOARD_SPECS))
    vit.add_argument("action", choices=["build", "boot"])
    vit.add_argument("--hardware", type=Path, help="Hardware export directory")
    vit.add_argument("--workspace", type=Path, help="Custom Vitis workspace path")
    _add_toolchain_args(vit, vitis=True)

    jtag = sub.add_parser("jtag", help="Download FSBL, PMUFW, bitstream, and ELF via JTAG")
    jtag.add_argument("board", choices=sorted(BOARD_SPECS))
    jtag.add_argument("--hardware", type=Path, help="Hardware export directory")
    jtag.add_argument("--workspace", type=Path, help="Custom Vitis workspace path")
    jtag.add_argument("--server", default="tcp:127.0.0.1:3121")
    jtag.add_argument("--cable", default="*")
    _add_toolchain_args(jtag, vitis=True)

    ser = sub.add_parser("serial", help="Capture board UART diagnostics (and optionally run JTAG)")
    ser.add_argument("board", choices=sorted(BOARD_SPECS))
    ser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments forwarded to serial_test.py")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "toolchains":
        print(format_toolchains(discover_toolchains(args.product)))
        return 0
    if args.command == "config":
        forwarded = args.args[1:] if args.args[:1] == ["--"] else args.args
        return run_template_config(args.board, forwarded)
    if args.command == "vivado":
        return run_vivado_action(
            args.board,
            args.action,
            config_dir=args.config_dir,
            vivado_dir=args.vivado_dir,
            tool_version=args.tool_version,
            strict_version=args.strict_version,
        )
    if args.command == "matrix":
        return run_matrix_check(
            args.board,
            args.profiles,
            vivado_dir=args.vivado_dir,
            tool_version=args.tool_version,
            strict_version=args.strict_version,
        )
    if args.command == "vitis":
        return run_vitis_action(
            args.board,
            args.action,
            hardware=args.hardware,
            workspace=args.workspace,
            vitis_dir=args.vitis_dir,
            tool_version=args.tool_version,
        )
    if args.command == "jtag":
        out_dir = run_jtag_download(
            args.board,
            hardware=args.hardware,
            workspace=args.workspace,
            server=args.server,
            cable=args.cable,
            vitis_dir=args.vitis_dir,
            tool_version=args.tool_version,
        )
        print(f"JTAG download finished. Output directory: {out_dir}")
        return 0
    if args.command == "serial":
        import shutil
        import subprocess
        spec = BOARD_SPECS[args.board]
        script = REPO_ROOT / spec["vitis_dir"] / "scripts" / "serial_test.py"
        forwarded = args.args[1:] if args.args[:1] == ["--"] else args.args
        uv = shutil.which("uv")
        if uv:
            return subprocess.run([uv, "run", "--with", "pyserial", "python", str(script), *forwarded]).returncode
        return subprocess.run([sys.executable, str(script), *forwarded]).returncode
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
