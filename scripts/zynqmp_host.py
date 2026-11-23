"""Cross-platform toolchain discovery, build dispatch, and JTAG/boot helpers."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import string
import subprocess
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATED_VERSION = "2023.1"

BOARD_SPECS = {
    "fz5": {
        "template_dir": "fz5_template",
        "vitis_dir": "fz5_vitis",
        "config_cli": "fz5_config",
        "design_name": "fz5_system",
        "platform_name": "fz5_platform",
        "app_name": "fz5_diagnostics",
        "xsa_name": "fz5_system.xsa",
        "bit_name": "fz5_system.bit",
        "elf_name": "fz5_diagnostics.elf",
        "default_profile": "fz5d",
        "matrix_profiles": ("fz5c", "minimal", "full"),
    },
    "axu4ev": {
        "template_dir": "axu4ev_template",
        "vitis_dir": "axu4ev_vitis",
        "config_cli": "axu4ev_config",
        "design_name": "axu4ev_system",
        "platform_name": "axu4ev_platform",
        "app_name": "axu4ev_diagnostics",
        "xsa_name": "axu4ev_system.xsa",
        "bit_name": "axu4ev_system.bit",
        "elf_name": "axu4ev_diagnostics.elf",
        "default_profile": "axu4ev",
        "matrix_profiles": ("minimal",),
    },
}


@dataclass(frozen=True)
class ToolchainInstall:
    """Represents one discovered Vivado or Vitis installation."""

    product: str
    version: str
    root: Path
    source: str
    has_xsct: bool = False
    has_bootgen: bool = False

    @property
    def is_validated(self) -> bool:
        return self.version == VALIDATED_VERSION

    def tool_path(self, tool_name: str, *, is_windows: bool | None = None) -> Path:
        """Return the OS-appropriate wrapper path under <root>/bin."""
        win = (os.name == "nt") if is_windows is None else is_windows
        suffix = ".bat" if win else ""
        return self.root / "bin" / f"{tool_name}{suffix}"


def _version_sort_key(version: str) -> tuple[int, tuple[tuple[int, int | str], ...], str]:
    """Order semantic/year versions cleanly when sorting descending."""
    parts: list[tuple[int, int | str]] = []
    for token in re.findall(r"\d+|[a-zA-Z]+", version):
        parts.append((1, int(token)) if token.isdigit() else (0, token.lower()))
    parsed = 1 if parts else 0
    return (parsed, tuple(parts), version)


def _extract_version(root: Path, product: str) -> str:
    """Infer Vivado/Vitis version from standard install directory layout."""
    name = root.name
    parent = root.parent.name
    if re.match(r"^\d{4}\.\d+", name):
        return name
    if name.lower() == product.lower() and re.match(r"^\d{4}\.\d+", parent):
        return parent
    version_file = root / ".xinstall" / f"{product}_{name}" / "data" / "installed.xml"
    if not version_file.is_file():
        return name if re.search(r"\d", name) else "unknown"
    return name


def _check_install(root: Path, product: str, source: str, *, is_windows: bool | None = None) -> ToolchainInstall | None:
    """Validate whether root looks like a runnable Vivado or Vitis install."""
    win = (os.name == "nt") if is_windows is None else is_windows
    suffix = ".bat" if win else ""
    bin_dir = root / "bin"
    if not bin_dir.is_dir():
        return None
    if product == "Vivado":
        if not (bin_dir / f"vivado{suffix}").is_file():
            return None
        return ToolchainInstall(
            product="Vivado",
            version=_extract_version(root, "Vivado"),
            root=root,
            source=source,
            has_bootgen=(bin_dir / f"bootgen{suffix}").is_file(),
        )
    has_xsct = (bin_dir / f"xsct{suffix}").is_file()
    has_vitis = (bin_dir / f"vitis{suffix}").is_file()
    if not (has_xsct or has_vitis):
        return None
    return ToolchainInstall(
        product="Vitis",
        version=_extract_version(root, "Vitis"),
        root=root,
        source=source,
        has_xsct=has_xsct,
        has_bootgen=(bin_dir / f"bootgen{suffix}").is_file(),
    )


def default_search_bases(*, is_windows: bool | None = None) -> list[Path]:
    """Return standard Xilinx/AMD installation base directories for the host OS."""
    win = (os.name == "nt") if is_windows is None else is_windows
    bases: list[Path] = []
    if win:
        drives = [f"{d}:/" for d in string.ascii_uppercase if Path(f"{d}:/").exists()]
        for drive in drives:
            for vendor in ("Xilinx", "xilinx", "AMD", "Program Files/Xilinx", "Program Files/AMD"):
                candidate = Path(drive) / vendor
                if candidate.is_dir():
                    bases.append(candidate)
    else:
        home = Path.home()
        for candidate in (
            Path("/tools/Xilinx"),
            Path("/tools/AMD"),
            Path("/opt/Xilinx"),
            Path("/opt/AMD"),
            Path("/usr/local/Xilinx"),
            Path("/usr/local/AMD"),
            home / "Xilinx",
            home / "AMD",
        ):
            if candidate.is_dir():
                bases.append(candidate)
    return bases


def _candidate_roots_from_base(base: Path, product: str) -> Iterable[Path]:
    """Yield candidate installs under <base>/<Product>/<ver> and <base>/<ver>/<Product>."""
    for prod_name in (product, product.lower()):
        product_dir = base / prod_name
        if product_dir.is_dir():
            for child in sorted(product_dir.iterdir()):
                if child.is_dir():
                    yield child
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        if re.match(r"^\d{4}\.\d+", child.name):
            for prod_name in (product, product.lower()):
                nested = child / prod_name
                if nested.is_dir():
                    yield nested


def discover_toolchains(
    product: str | None = None,
    *,
    env: dict[str, str] | None = None,
    search_bases: Iterable[Path] | None = None,
    is_windows: bool | None = None,
) -> list[ToolchainInstall]:
    """Discover all installed Vivado/Vitis toolchains without hardcoding paths."""
    env_map = os.environ if env is None else env
    win = (os.name == "nt") if is_windows is None else is_windows
    products = [product] if product else ["Vivado", "Vitis"]
    found: dict[tuple[str, str], ToolchainInstall] = {}

    def record(item: ToolchainInstall | None) -> None:
        if item is None:
            return
        key = (item.product, str(item.root.resolve()) if item.root.exists() else str(item.root))
        found.setdefault(key, item)

    env_keys = {
        "Vivado": ("XILINX_VIVADO", "AMD_VIVADO"),
        "Vitis": ("XILINX_VITIS", "AMD_VITIS"),
    }
    path_bins = {
        "Vivado": ("vivado.bat" if win else "vivado",),
        "Vitis": ("xsct.bat" if win else "xsct", "vitis.bat" if win else "vitis"),
    }

    for prod in products:
        for var in env_keys[prod]:
            raw = env_map.get(var, "").strip()
            if raw:
                record(_check_install(Path(raw), prod, f"env:{var}", is_windows=win))

        if env is None:
            for binary in path_bins[prod]:
                located = shutil.which(binary)
                if located:
                    exe_path = Path(located).resolve()
                    for parent in exe_path.parents:
                        inst = _check_install(parent, prod, "PATH", is_windows=win)
                        if inst is not None:
                            record(inst)
                            break

        bases = list(default_search_bases(is_windows=win) if search_bases is None else search_bases)
        for base in bases:
            if not base.is_dir():
                continue
            for cand in _candidate_roots_from_base(base, prod):
                record(_check_install(cand, prod, "scan", is_windows=win))

    items = list(found.values())
    items.sort(key=lambda x: (x.product, not x.is_validated, _version_sort_key(x.version)), reverse=False)
    # Sort descending within each product while keeping validated 2023.1 listed clearly.
    ordered: list[ToolchainInstall] = []
    for prod in products:
        group = [i for i in items if i.product == prod]
        group.sort(key=lambda x: (x.is_validated, _version_sort_key(x.version)), reverse=True)
        ordered.extend(group)
    return ordered


def select_toolchain(
    product: str,
    *,
    tool_dir: Path | str | None = None,
    tool_version: str | None = None,
    env: dict[str, str] | None = None,
    search_bases: Iterable[Path] | None = None,
    is_windows: bool | None = None,
) -> ToolchainInstall:
    """Select an installation by explicit path, requested version, env, or discovered default."""
    env_map = os.environ if env is None else env
    win = (os.name == "nt") if is_windows is None else is_windows

    if tool_dir:
        candidate = Path(tool_dir).expanduser().resolve()
        inst = _check_install(candidate, product, "explicit-dir", is_windows=win)
        if inst is None:
            raise FileNotFoundError(f"Invalid {product} directory: {candidate}")
        return inst

    requested_ver = tool_version or env_map.get(f"ZYNQMP_{product.upper()}_VERSION", "").strip() or None
    installs = discover_toolchains(product, env=env_map, search_bases=search_bases, is_windows=win)
    if not installs:
        raise FileNotFoundError(
            f"No {product} installation found. Set XILINX_{product.upper()} or pass --{product.lower()}-dir / --tool-version."
        )

    if requested_ver:
        matches = [i for i in installs if i.version == requested_ver]
        if not matches:
            available = ", ".join(f"{i.version} ({i.root})" for i in installs)
            raise FileNotFoundError(f"{product} {requested_ver} not found. Installed: {available}")
        return matches[0]

    env_matches = [i for i in installs if i.source.startswith("env:") or i.source == "PATH"]
    if env_matches:
        return env_matches[0]

    validated = [i for i in installs if i.is_validated]
    if validated:
        return validated[0]

    return installs[0]


def format_toolchains(installs: list[ToolchainInstall]) -> str:
    """Format discovered installations for console listing."""
    if not installs:
        return "No Vivado or Vitis installations detected. Set XILINX_VIVADO / XILINX_VITIS or pass --vivado-dir / --vitis-dir."
    lines = ["Detected toolchains:"]
    for item in installs:
        tags = []
        if item.is_validated:
            tags.append("validated")
        if item.product == "Vitis":
            tags.append("xsct" if item.has_xsct else "no-xsct")
            if item.has_bootgen:
                tags.append("bootgen")
        if item.source != "scan":
            tags.append(item.source)
        tag_str = f" [{' | '.join(tags)}]" if tags else ""
        lines.append(f"  {item.product:<6} {item.version:<10} {item.root}{tag_str}")
    return "\n".join(lines)


def find_python(template_root: Path | None = None, *, board: str | None = None) -> str:
    """Locate a Python 3 interpreter across Windows and Linux."""
    env_candidates = ["ZYNQMP_PYTHON"]
    if board == "fz5":
        env_candidates.insert(0, "FZ5_PYTHON")
    elif board == "axu4ev":
        env_candidates.insert(0, "AXU4EV_PYTHON")
    for var in env_candidates:
        val = os.environ.get(var, "").strip()
        if val:
            return val
    if template_root is not None:
        for rel in (Path(".venv/Scripts/python.exe"), Path(".venv/bin/python")):
            cand = template_root / rel
            if cand.is_file():
                return str(cand)
    return sys.executable or shutil.which("python3") or shutil.which("python") or "python"


def _clean_tool_env(install: ToolchainInstall) -> dict[str, str]:
    """Prepare a clean child environment for launching Vivado/Vitis wrappers."""
    env = os.environ.copy()
    if install.product == "Vivado":
        env["XILINX_VIVADO"] = str(install.root)
    else:
        env["XILINX_VITIS"] = str(install.root)
        env["XILINX_SDK"] = str(install.root)
    bin_dir = str(install.root / "bin")
    path_parts = env.get("PATH", "").split(os.pathsep) if env.get("PATH") else []
    if bin_dir not in path_parts:
        env["PATH"] = os.pathsep.join([bin_dir, *path_parts]) if path_parts else bin_dir
    return env


def run_command_tee(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path | None = None,
) -> int:
    """Run a command, streaming stdout/stderr live and optionally writing a UTF-8 log."""
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log_file.write(line)
            return proc.wait()
    completed = subprocess.run(cmd, cwd=str(cwd), env=env)
    return completed.returncode


def file_sha256(path: Path) -> str:
    """Compute uppercase SHA256 hex digest matching build-record conventions."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_template_config(
    board: str,
    args: list[str],
    *,
    repo_root: Path = REPO_ROOT,
) -> int:
    """Run a template's Python configuration CLI (fz5-config / axu4ev-config)."""
    spec = BOARD_SPECS[board]
    template_root = repo_root / spec["template_dir"]
    uv = shutil.which("uv")
    if uv:
        cmd = [uv, "run", "--project", str(template_root), f"{board}-config", *args]
        return subprocess.run(cmd, cwd=str(template_root)).returncode
    py = find_python(template_root, board=board)
    return subprocess.run([py, str(template_root / "config.py"), *args], cwd=str(template_root)).returncode


def run_vivado_action(
    board: str,
    action: str,
    *,
    config_dir: Path | None = None,
    vivado_dir: Path | str | None = None,
    tool_version: str | None = None,
    strict_version: bool = False,
    repo_root: Path = REPO_ROOT,
    log_name: str | None = None,
) -> int:
    """Invoke Vivado in batch mode to build project or bitstream cross-platform."""
    if action not in ("project", "bitstream"):
        raise ValueError(f"Unsupported Vivado action: {action}")
    spec = BOARD_SPECS[board]
    template_root = repo_root / spec["template_dir"]
    install = select_toolchain("Vivado", tool_dir=vivado_dir, tool_version=tool_version)
    if not install.is_validated:
        print(
            f"Note: validated Vivado version is {VALIDATED_VERSION}; using {install.version} at {install.root}.",
            file=sys.stderr,
        )
    env = _clean_tool_env(install)
    if strict_version:
        env["ZYNQMP_STRICT_VERSION"] = "1"
    # Pass explicit python path to export_routed.tcl so it finds the template's python cleanly.
    env.setdefault(f"{board.upper()}_PYTHON", find_python(template_root, board=board))

    build_dir = template_root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    log_path = build_dir / (log_name or f"{action}.log")
    tcl_args = [action]
    if config_dir is not None:
        tcl_args.append(str(config_dir))
    cmd = [
        str(install.tool_path("vivado")),
        "-mode",
        "batch",
        "-notrace",
        "-nojournal",
        "-log",
        str(log_path),
        "-source",
        str(template_root / "tcl" / "build.tcl"),
        "-tclargs",
        *tcl_args,
    ]
    rc = subprocess.run(cmd, cwd=str(template_root), env=env).returncode
    if rc != 0:
        raise RuntimeError(f"Vivado {action} failed (exit {rc}). See {log_path}")
    return rc


def run_matrix_check(
    board: str,
    profiles: list[str] | None = None,
    *,
    vivado_dir: Path | str | None = None,
    tool_version: str | None = None,
    strict_version: bool = False,
    repo_root: Path = REPO_ROOT,
) -> int:
    """Generate and build Vivado projects for multiple board defconfig profiles."""
    spec = BOARD_SPECS[board]
    template_root = repo_root / spec["template_dir"]
    chosen = profiles or list(spec["matrix_profiles"])
    for prof in chosen:
        if not (template_root / "configs" / f"{prof}_defconfig").is_file():
            raise FileNotFoundError(f"Unknown profile: {prof}")

    py = find_python(template_root, board=board)
    for prof in chosen:
        out_dir = template_root / ".work" / "matrix" / prof
        rc = subprocess.run(
            [
                py,
                str(template_root / "scripts" / "configure.py"),
                "generate",
                "--config",
                str(template_root / "configs" / f"{prof}_defconfig"),
                "--out",
                str(out_dir),
            ],
            cwd=str(template_root),
        ).returncode
        if rc != 0:
            raise RuntimeError(f"Configuration generation failed for profile {prof}")

    for prof in chosen:
        run_vivado_action(
            board,
            "project",
            config_dir=template_root / ".work" / "matrix" / prof,
            vivado_dir=vivado_dir,
            tool_version=tool_version,
            strict_version=strict_version,
            repo_root=repo_root,
            log_name=f"matrix-{prof}.log",
        )
    return 0


def resolve_vitis_paths(
    board: str,
    *,
    hardware: Path | str | None = None,
    workspace: Path | str | None = None,
    repo_root: Path = REPO_ROOT,
) -> tuple[Path, Path, Path, Path, Path, dict]:
    """Verify hardware bundle and compute resolved Vitis workspace/output paths."""
    spec = BOARD_SPECS[board]
    template_root = repo_root / spec["template_dir"]
    vitis_root = repo_root / spec["vitis_dir"]
    hw_dir = Path(hardware).resolve() if hardware else (template_root / "export").resolve()

    py = find_python(template_root, board=board)
    rc = subprocess.run([py, str(vitis_root / "scripts" / "verify_bundle.py"), str(hw_dir)], cwd=str(vitis_root)).returncode
    if rc != 0:
        raise RuntimeError(f"Hardware bundle verification failed for {hw_dir}")

    cfg = json.loads((hw_dir / "config.json").read_text(encoding="utf-8-sig"))
    ws_path = (
        Path(workspace).resolve()
        if workspace
        else (vitis_root / "build" / cfg["CONFIG_ID"][:12] / "workspace").resolve()
    )
    out_dir = ws_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    return template_root, vitis_root, hw_dir, ws_path, out_dir, cfg


def run_vitis_action(
    board: str,
    action: str,
    *,
    hardware: Path | str | None = None,
    workspace: Path | str | None = None,
    vitis_dir: Path | str | None = None,
    tool_version: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> int:
    """Build Vitis workspace/ELF or package BOOT.BIN cross-platform."""
    if action not in ("build", "boot"):
        raise ValueError(f"Unsupported Vitis action: {action}")
    spec = BOARD_SPECS[board]
    _, vitis_root, hw_dir, ws_path, out_dir, cfg = resolve_vitis_paths(
        board, hardware=hardware, workspace=workspace, repo_root=repo_root
    )
    install = select_toolchain("Vitis", tool_dir=vitis_dir, tool_version=tool_version)
    if not install.is_validated:
        print(
            f"Note: validated Vitis version is {VALIDATED_VERSION}; using {install.version} at {install.root}.",
            file=sys.stderr,
        )
    env = _clean_tool_env(install)

    if action == "build":
        if not install.has_xsct:
            raise RuntimeError(
                f"Vitis at {install.root} does not include classic xsct. Select Vitis 2023.1–2024.x with xsct."
            )
        rc = run_command_tee(
            [
                str(install.tool_path("xsct")),
                str(vitis_root / "scripts" / "create_workspace.tcl"),
                str(hw_dir),
                str(ws_path),
            ],
            cwd=vitis_root,
            env=env,
            log_path=out_dir / "vitis-build.log",
        )
        if rc != 0:
            raise RuntimeError(f"XSCT build failed (exit {rc}); see {out_dir / 'vitis-build.log'}")

        elf_src = ws_path / spec["app_name"] / "Debug" / spec["elf_name"]
        if not elf_src.is_file():
            raise FileNotFoundError(f"No diagnostic ELF produced at {elf_src}")
        elf_dst = out_dir / spec["elf_name"]
        shutil.copy2(elf_src, elf_dst)
        shutil.copy2(hw_dir / "config.json", out_dir / "config.json")
        record = {
            "config_id": cfg["CONFIG_ID"],
            "xsa_sha256": file_sha256(hw_dir / spec["xsa_name"]),
            "elf_sha256": file_sha256(elf_dst),
            "workspace": str(ws_path),
            "vitis_version": install.version,
        }
        (out_dir / "build-record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"Vitis workspace: {ws_path}")
        return 0

    record_path = out_dir / "build-record.json"
    if not record_path.is_file():
        raise FileNotFoundError(f"Missing build record {record_path}. Run build first.")
    record = json.loads(record_path.read_text(encoding="utf-8-sig"))
    elf_dst = out_dir / spec["elf_name"]
    if (
        record["config_id"] != cfg["CONFIG_ID"]
        or record["xsa_sha256"].lower() != file_sha256(hw_dir / spec["xsa_name"]).lower()
    ):
        raise RuntimeError("Stale Vitis build; rebuild from this XSA.")
    if record["elf_sha256"].lower() != file_sha256(elf_dst).lower():
        raise RuntimeError("Diagnostic ELF differs from build record.")
    if not workspace and record.get("workspace"):
        recorded = Path(record["workspace"])
        candidate_ws = out_dir / recorded.name
        if candidate_ws.is_dir():
            ws_path = candidate_ws

    export_root = ws_path / spec["platform_name"] / "export"
    fsbl = next(export_root.rglob("fsbl.elf"), None)
    pmufw = next(export_root.rglob("pmufw.elf"), None)
    if fsbl is None or pmufw is None:
        raise FileNotFoundError(f"Platform export under {export_root} must provide fsbl.elf and pmufw.elf.")

    bif_text = "\n".join([
        "the_ROM_image:",
        "{",
        f'  [bootloader, destination_cpu=a53-0] "{fsbl.as_posix()}"',
        f'  [pmufw_image] "{pmufw.as_posix()}"',
        f'  [destination_device=pl] "{(hw_dir / spec["bit_name"]).as_posix()}"',
        f'  [destination_cpu=a53-0, exception_level=el-3] "{elf_dst.as_posix()}"',
        "}",
        "",
    ])
    bif_path = out_dir / "boot.bif"
    bif_path.write_text(bif_text, encoding="ascii")

    if not install.has_bootgen:
        raise RuntimeError(f"bootgen not found in {install.root / 'bin'}")
    boot_bin = out_dir / "BOOT.BIN"
    rc = subprocess.run(
        [str(install.tool_path("bootgen")), "-arch", "zynqmp", "-image", str(bif_path), "-o", str(boot_bin), "-w", "on"],
        cwd=str(out_dir),
        env=env,
    ).returncode
    if rc != 0:
        raise RuntimeError(f"bootgen failed (exit {rc})")
    print(f"SD boot image: {boot_bin}")
    return 0


def run_jtag_download(
    board: str,
    *,
    hardware: Path | str | None = None,
    workspace: Path | str | None = None,
    server: str = "tcp:127.0.0.1:3121",
    cable: str = "*",
    vitis_dir: Path | str | None = None,
    tool_version: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Verify build artifacts and download FSBL/PMUFW/bitstream/ELF over JTAG via XSCT."""
    spec = BOARD_SPECS[board]
    _, vitis_root, hw_dir, ws_path, out_dir, cfg = resolve_vitis_paths(
        board, hardware=hardware, workspace=workspace, repo_root=repo_root
    )
    record = json.loads((out_dir / "build-record.json").read_text(encoding="utf-8-sig"))
    elf_dst = out_dir / spec["elf_name"]
    if (
        record["config_id"] != cfg["CONFIG_ID"]
        or record["xsa_sha256"].lower() != file_sha256(hw_dir / spec["xsa_name"]).lower()
        or record["elf_sha256"].lower() != file_sha256(elf_dst).lower()
    ):
        raise RuntimeError("ELF/XSA/config hash mismatch. Rebuild Vitis first.")
    if not workspace and record.get("workspace"):
        candidate_ws = out_dir / Path(record["workspace"]).name
        if candidate_ws.is_dir():
            ws_path = candidate_ws

    install = select_toolchain("Vitis", tool_dir=vitis_dir, tool_version=tool_version)
    if not install.has_xsct:
        raise RuntimeError(f"Vitis at {install.root} does not include classic xsct.")
    env = _clean_tool_env(install)
    rc = run_command_tee(
        [
            str(install.tool_path("xsct")),
            str(vitis_root / "scripts" / "run_jtag.tcl"),
            str(hw_dir),
            str(ws_path),
            server,
            cable,
        ],
        cwd=vitis_root,
        env=env,
        log_path=out_dir / "jtag.log",
    )
    if rc != 0:
        raise RuntimeError(f"JTAG download failed (exit {rc}); see {out_dir / 'jtag.log'}")
    return out_dir
