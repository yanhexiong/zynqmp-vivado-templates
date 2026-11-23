"""Cross-platform AXU4EV-F Vitis workspace/ELF build and BOOT.BIN packager."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from zynqmp_host import discover_toolchains, format_toolchains, run_vitis_action


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cross-platform AXU4EV-F Vitis build and BOOT.BIN packager")
    p.add_argument("action", nargs="?", default="build", choices=["build", "boot", "toolchains"])
    p.add_argument("--hardware", type=Path, help="Hardware export directory")
    p.add_argument("--workspace", type=Path, help="Custom Vitis workspace path")
    p.add_argument("--tool-version", help="Select installed Vitis version (e.g. 2023.1, 2024.1)")
    p.add_argument("--vitis-dir", type=Path, help="Explicit Vitis installation directory")
    args = p.parse_args(argv)

    if args.action == "toolchains":
        print(format_toolchains(discover_toolchains("Vitis")))
        return 0
    return run_vitis_action(
        "axu4ev",
        args.action,
        hardware=args.hardware,
        workspace=args.workspace,
        vitis_dir=args.vitis_dir,
        tool_version=args.tool_version,
        repo_root=REPO_ROOT,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
