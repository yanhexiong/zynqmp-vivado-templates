"""Cross-platform FZ5 template CLI (config, Vivado project/bitstream, matrix check)."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from zynqmp_host import (
    discover_toolchains,
    find_python,
    format_toolchains,
    run_matrix_check,
    run_template_config,
    run_vivado_action,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cross-platform FZ5 Vivado template runner")
    p.add_argument(
        "action",
        nargs="?",
        default="help",
        choices=["help", "toolchains", "defconfig", "menuconfig", "generate", "project", "bitstream", "matrix", "check"],
    )
    p.add_argument("--profile", default="fz5d", help="Profile for defconfig (fz5d, fz5c, minimal, full)")
    p.add_argument("--profiles", nargs="+", help="Profiles for matrix check")
    p.add_argument("--config-dir", type=Path, help="Custom generated config directory for project/bitstream")
    p.add_argument("--tool-version", help="Select installed Vivado version (e.g. 2023.1, 2024.1)")
    p.add_argument("--vivado-dir", type=Path, help="Explicit Vivado installation directory")
    p.add_argument("--strict-version", action="store_true", help="Require exact Vivado 2023.1")
    args = p.parse_args(argv)

    if args.action == "help":
        print("python scripts/fz5.py <action> [options]")
        print("Actions: toolchains, defconfig, menuconfig, generate, project, bitstream, matrix, check")
        print("Portable editor: uv run fz5-config (from fz5_template)")
        print("Vivado Tcl Console: source {fz5_template/tcl/init_project.tcl}")
        return 0
    if args.action == "toolchains":
        print(format_toolchains(discover_toolchains("Vivado")))
        return 0
    if args.action == "check":
        py = find_python(ROOT, board="fz5")
        return subprocess.run([py, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=str(ROOT)).returncode
    if args.action == "defconfig":
        return run_template_config("fz5", ["defconfig", "--profile", args.profile], repo_root=REPO_ROOT)
    if args.action in ("menuconfig", "generate"):
        return run_template_config("fz5", [args.action], repo_root=REPO_ROOT)
    if args.action == "matrix":
        return run_matrix_check(
            "fz5",
            args.profiles,
            vivado_dir=args.vivado_dir,
            tool_version=args.tool_version,
            strict_version=args.strict_version,
            repo_root=REPO_ROOT,
        )
    return run_vivado_action(
        "fz5",
        args.action,
        config_dir=args.config_dir,
        vivado_dir=args.vivado_dir,
        tool_version=args.tool_version,
        strict_version=args.strict_version,
        repo_root=REPO_ROOT,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
