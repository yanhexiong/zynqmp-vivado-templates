"""Kconfig configuration library and portable console editor; no build dispatch."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/vendor"))
import kconfiglib as kc
from fz5_config.i18n import ConfigError, Translator


def load_config(path: Path | None = None) -> kc.Kconfig:
    if path is not None and not path.is_file():
        raise ConfigError("config_missing", path=path)
    os.environ["srctree"] = str(ROOT)
    k = kc.Kconfig(str(ROOT / "Kconfig"), warn_to_stderr=False)
    path = path or ROOT / ".config"
    if path.exists():
        k.load_config(str(path))
    if k.warnings:
        raise ConfigError("config_warning", detail="\n".join(k.warnings))
    # Kconfig normally silently replaces out-of-range ints with defaults.
    # Reject that here: a changed memory allocation must never go unnoticed.
    for s in k.unique_defined_syms:
        if s.type in (kc.INT, kc.HEX) and s.user_value is not None:
            if int(s.user_value, 0 if s.type == kc.HEX else 10) != int(s.str_value, 0 if s.type == kc.HEX else 10):
                raise ConfigError("range_error", name=s.name, value=s.user_value)
    return k


def values(k: kc.Kconfig) -> dict:
    for s in k.unique_defined_syms:
        if s.type == kc.INT and s.user_value is not None and int(s.user_value) != int(s.str_value):
            raise ConfigError("range_error", name=s.name, value=s.user_value)
    v = {}
    for s in k.unique_defined_syms:
        v[s.name] = (s.tri_value == 2) if s.type == kc.BOOL else int(s.str_value) if s.type == kc.INT else s.str_value
    total = 8 if v["BOARD_FZ5D"] else 4
    reserve = v["PL_RESERVED_MB"] * 1024**2
    if v["PL_RESERVED_MB"] % 64:
        raise ConfigError("pool_alignment")
    if reserve > (total - 2) * 1024**3:
        raise ConfigError("pool_too_large")
    high_base = 0x800000000
    high_size = (total - 2) * 1024**3
    v.update(BOARD_NAME="FZ5D" if total == 8 else "FZ5C",
             PART=f"xczu5ev-sfvc784-{'1' if v['SPEED_1'] else '2'}-i",
             DDR_TOTAL_BYTES=total * 1024**3, DDR_LOW_BASE=0,
             DDR_LOW_SIZE=0x80000000, DDR_HIGH_BASE=high_base,
             DDR_HIGH_SIZE=high_size, PS_AVAILABLE_BYTES=total * 1024**3 - reserve,
             PL_POOL_BASE=high_base + high_size - reserve if reserve else 0,
             PL_POOL_SIZE=reserve, RUN_LED_MIO=43, FAN_CTRL_MIO=42,
             GPIO_BASE=0xA0000000, BRAM_BASE=0xA0010000, BRAM_SIZE=0x10000,
             DMA_BASE=0xA0020000, RS232_BASE=0xA0030000)
    raw = json.dumps(v, sort_keys=True, separators=(",", ":")).encode()
    v["CONFIG_ID"] = hashlib.sha256(raw).hexdigest()
    return v


def tcl_quote(text: str) -> str:
    """One Tcl word, including literal backslashes, dollars and brackets."""
    replacements = {"\\": "\\\\", '"': '\\"', "$": "\\$", "[": "\\[", "]": "\\]", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    return '"' + "".join(replacements.get(c, c) for c in text) + '"'


def set_values(k: kc.Kconfig, assignments: list[str]) -> None:
    """Validate the complete requested change before callers write any files."""
    requested = {}
    for assignment in assignments:
        name, sep, raw = assignment.partition("=")
        name = name.removeprefix("CONFIG_")
        if not sep or name not in k.syms or not k.syms[name].nodes:
            raise ConfigError("unknown_setting", assignment=assignment)
        if name in requested:
            raise ConfigError("duplicate_setting", name=name)
        s = k.syms[name]
        if not any(n.prompt for n in s.nodes):
            raise ConfigError("fixed_setting", name=name)
        if s.type == kc.BOOL:
            aliases = {"y": "y", "yes": "y", "true": "y", "1": "y", "启用": "y", "是": "y", "n": "n", "no": "n", "false": "n", "0": "n", "禁用": "n", "否": "n"}
            if raw.lower() not in aliases:
                raise ConfigError("bool_expected", name=name)
            normalized = aliases[raw.lower()]
        elif s.type == kc.INT:
            try:
                normalized = str(int(raw, 10))
            except ValueError:
                raise ConfigError("int_expected", name=name) from None
        else:
            raise ConfigError("unsupported_type", name=name)
        requested[name] = normalized
        if not s.set_value(normalized):
            raise ConfigError("invalid_value", name=name, value=raw)
    values(k)
    for name, expected in requested.items():
        s = k.syms[name]
        if s.str_value != expected:
            dependency = kc.expr_str(s.direct_dep)
            raise ConfigError("dependency_error", name=name, value=expected, dependency=dependency, effective=s.str_value)


def generate(k: kc.Kconfig, out: Path, save: bool = True, config_path: Path | None = None, ui: Translator | None = None, quiet: bool = False) -> dict:
    v = values(k)
    out.mkdir(parents=True, exist_ok=True)
    source_path, source_text = "", ""
    if save:
        target = (config_path or ROOT / ".config").resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        k.write_config(str(target))
        try:
            source_path = Path(os.path.relpath(target, ROOT)).as_posix()
        except ValueError:  # a custom file on a different Windows drive
            source_path = target.as_posix()
        source_text = target.read_text(encoding="utf-8-sig")
    (out / "config.json").write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
    tcl = ["# Generated by the Python configuration editor. Do not edit.",
           "set fz5_config_format 1",
           f"set fz5_config_source {tcl_quote(source_path)}",
           f"set fz5_config_source_text {tcl_quote(source_text)}",
           "array set cfg {"]
    header = ["/* Generated from Kconfig. Do not edit. */", "#ifndef FZ5_CONFIG_H", "#define FZ5_CONFIG_H", "#include <stdint.h>"]
    for n, x in v.items():
        if isinstance(x, bool):
            t, c = str(int(x)), str(int(x))
        elif isinstance(x, int):
            t, c = str(x), f"UINT64_C({hex(x)})" if x >= 2**32 else hex(x)
        else:
            t, c = "{" + x + "}", json.dumps(x)
        tcl.append(f"    {n} {t}")
        header.append(f"#define FZ5_{n} {c}")
    tcl.append("}")
    header.append("#endif")
    (out / "config.tcl").write_text("\n".join(tcl) + "\n", encoding="utf-8")
    (out / "fz5_config.h").write_text("\n".join(header) + "\n", encoding="utf-8")
    dts = ["/* Include inside a ZynqMP system-user.dtsi. DDR is shared with PL.",
           f" * CONFIG_ID: {v['CONFIG_ID']}",
           " * no-map reserves ownership; it does not enforce AXI isolation. */",
           "/ {", f'    fz5-config-id = "{v["CONFIG_ID"]}";']
    if reserve := v["PL_POOL_SIZE"]:
        base = v["PL_POOL_BASE"]
        dts.extend(["    reserved-memory {", "        #address-cells = <2>;", "        #size-cells = <2>;", "        ranges;",
                    f"        fz5_pl_pool: pl-pool@{base:x} {{", "            no-map;",
                    f"            reg = <0x{base >> 32:x} 0x{base & 0xffffffff:08x} 0x{reserve >> 32:x} 0x{reserve & 0xffffffff:08x}>;",
                    "        };", "    };"])
    dts.append("};")
    (out / "fz5-memory.dtsi").write_text("\n".join(dts) + "\n", encoding="utf-8")
    if not quiet:
        print((ui or Translator()).t("summary", board=v["BOARD_NAME"], part=v["PART"], ps=v["PS_AVAILABLE_BYTES"] // 2**20, pl=v["PL_RESERVED_MB"], id=v["CONFIG_ID"][:12]))
    return v



def main() -> None:
    # Keep the historical script path, using the same full-screen editor.
    from fz5_config.cli import entrypoint
    entrypoint()


if __name__ == "__main__":
    main()
