"""Kconfig model and portable configuration exporter for AXU4EV-F."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "vendor"))
import kconfiglib as kc
from axu4ev_config.i18n import ConfigError, Translator


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
    for symbol in k.unique_defined_syms:
        if symbol.type in (kc.INT, kc.HEX) and symbol.user_value is not None:
            base = 0 if symbol.type == kc.HEX else 10
            if int(symbol.user_value, base) != int(symbol.str_value, base):
                raise ConfigError("range_error", name=symbol.name, value=symbol.user_value)
    return k


def values(k: kc.Kconfig) -> dict:
    v = {}
    for symbol in k.unique_defined_syms:
        if symbol.type == kc.BOOL:
            v[symbol.name] = symbol.tri_value == 2
        elif symbol.type == kc.INT:
            v[symbol.name] = int(symbol.str_value)
        else:
            v[symbol.name] = symbol.str_value
    reserve_mb = v["PL_RESERVED_MB"]
    if reserve_mb % 64:
        raise ConfigError("pool_alignment")

    ddr_low_base = 0x00000000
    ddr_low_size = 0x80000000
    ddr_high_base = 0x800000000
    ddr_high_size = 0x80000000
    reserve_bytes = reserve_mb * 1024**2
    if reserve_bytes > ddr_high_size:
        raise ConfigError("pool_too_large")
    v.update(
        BOARD_NAME="AXU4EV-F",
        PART="xczu4ev-sfvc784-2-i",
        DDR_TOTAL_BYTES=4 * 1024**3,
        DDR_LOW_BASE=ddr_low_base,
        DDR_LOW_SIZE=ddr_low_size,
        DDR_HIGH_BASE=ddr_high_base,
        DDR_HIGH_SIZE=ddr_high_size,
        DDR_HIGH_PHYSICAL_END=ddr_high_base + ddr_high_size - 1,
        DDR_HIGH_AXI_APERTURE_BASE=ddr_high_base,
        DDR_HIGH_AXI_APERTURE_END=0xFFFFFFFFF,
        DDR_HIGH_AXI_APERTURE_SIZE=0x800000000,
        PS_AVAILABLE_BYTES=4 * 1024**3 - reserve_bytes,
        PL_POOL_BASE=ddr_high_base + ddr_high_size - reserve_bytes if reserve_bytes else 0,
        PL_POOL_SIZE=reserve_bytes,
        PL_RESERVED_MB=reserve_mb,
        GPIO_BASE=0xA0000000,
        BRAM_BASE=0xA0010000,
        BRAM_SIZE=0x10000,
        DMA_BASE=0xA0020000,
        UART_BASE=0xA0030000,
        LED0_MIO=39,
        LED1_MIO=40,
        LED_ACTIVE_HIGH=True,
        PHY_ID1=0x001C,
        PHY_ID2=0xC916,
        PHY_ID_MASK=0x001FFFFF,
        EEPROM_ADDR_BLOCK0=0x50,
        EEPROM_ADDR_BLOCK1=0x51,
        PHY_MDIO_ADDR=1,
        QSPI_JEDEC_ID=0x20BB19,
        QSPI_SIZE_BYTES=32 * 1024**2,
    )
    raw = json.dumps(v, sort_keys=True, separators=(",", ":")).encode("utf-8")
    v["CONFIG_ID"] = hashlib.sha256(raw).hexdigest()
    return v


def tcl_quote(text: str) -> str:
    replacements = {
        "\\": "\\\\", '"': '\\"', "$": "\\$", "[": "\\[", "]": "\\]",
        "\n": "\\n", "\r": "\\r", "\t": "\\t",
    }
    return '"' + "".join(replacements.get(char, char) for char in text) + '"'


def set_values(k: kc.Kconfig, assignments: list[str]) -> None:
    requested = {}
    for assignment in assignments:
        name, sep, raw = assignment.partition("=")
        name = name.removeprefix("CONFIG_")
        if not sep or name not in k.syms or not k.syms[name].nodes:
            raise ConfigError("unknown_setting", assignment=assignment)
        if name in requested:
            raise ConfigError("duplicate_setting", name=name)
        symbol = k.syms[name]
        if not any(node.prompt for node in symbol.nodes):
            raise ConfigError("fixed_setting", name=name)
        if symbol.type == kc.BOOL:
            aliases = {
                "y": "y", "yes": "y", "true": "y", "1": "y", "启用": "y", "是": "y",
                "n": "n", "no": "n", "false": "n", "0": "n", "禁用": "n", "否": "n",
            }
            if raw.lower() not in aliases:
                raise ConfigError("bool_expected", name=name)
            normalized = aliases[raw.lower()]
        elif symbol.type == kc.INT:
            try:
                normalized = str(int(raw, 10))
            except ValueError:
                raise ConfigError("int_expected", name=name) from None
        else:
            raise ConfigError("unsupported_type", name=name)
        requested[name] = normalized
        if not symbol.set_value(normalized):
            raise ConfigError("invalid_value", name=name, value=raw)

    values(k)
    for name, expected in requested.items():
        symbol = k.syms[name]
        if symbol.str_value != expected:
            dependency = kc.expr_str(symbol.direct_dep)
            raise ConfigError(
                "dependency_error", name=name, value=expected,
                dependency=dependency, effective=symbol.str_value,
            )


def generate(
    k: kc.Kconfig,
    out: Path,
    save: bool = True,
    config_path: Path | None = None,
    ui: Translator | None = None,
    quiet: bool = False,
) -> dict:
    v = values(k)
    out.mkdir(parents=True, exist_ok=True)
    source_path, source_text = "", ""
    if save:
        target = (config_path or ROOT / ".config").resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        k.write_config(str(target))
        try:
            source_path = Path(os.path.relpath(target, ROOT)).as_posix()
        except ValueError:
            source_path = target.as_posix()
        source_text = target.read_text(encoding="utf-8-sig")

    (out / "config.json").write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
    tcl = [
        "# Generated by the Python configuration editor. Do not edit.",
        "set axu4ev_config_format 1",
        f"set axu4ev_config_source {tcl_quote(source_path)}",
        f"set axu4ev_config_source_text {tcl_quote(source_text)}",
        "array set cfg {",
    ]
    header = [
        "/* Generated from Kconfig. Do not edit. */",
        "#ifndef AXU4EV_CONFIG_H",
        "#define AXU4EV_CONFIG_H",
        "#include <stdint.h>",
    ]
    for name, value in v.items():
        if isinstance(value, bool):
            tcl_value, c_value = str(int(value)), str(int(value))
        elif isinstance(value, int):
            tcl_value = str(value)
            c_value = f"UINT64_C({hex(value)})" if value >= 2**32 else hex(value)
        else:
            tcl_value, c_value = "{" + value + "}", json.dumps(value)
        tcl.append(f"    {name} {tcl_value}")
        header.append(f"#define AXU4EV_{name} {c_value}")
    tcl.append("}")
    header.append("#endif")
    (out / "config.tcl").write_text("\n".join(tcl) + "\n", encoding="utf-8")
    (out / "axu4ev_config.h").write_text("\n".join(header) + "\n", encoding="utf-8")

    dts = [
        "/* Include from system-user.dtsi. PL shares the PS DDR controller.",
        f" * CONFIG_ID: {v['CONFIG_ID']}",
        " * no-map reserves software ownership; it does not enforce AXI isolation. */",
        "/ {",
        f'    axu4ev-config-id = "{v["CONFIG_ID"]}";',
    ]
    if v["PL_POOL_SIZE"]:
        base, size = v["PL_POOL_BASE"], v["PL_POOL_SIZE"]
        dts.extend([
            "    reserved-memory {",
            "        #address-cells = <2>;",
            "        #size-cells = <2>;",
            "        ranges;",
            f"        axu4ev_pl_pool: pl-pool@{base:x} {{",
            "            no-map;",
            f"            reg = <0x{base >> 32:x} 0x{base & 0xffffffff:08x} 0x{size >> 32:x} 0x{size & 0xffffffff:08x}>;",
            "        };",
            "    };",
        ])
    dts.append("};")
    (out / "axu4ev-memory.dtsi").write_text("\n".join(dts) + "\n", encoding="utf-8")

    if not quiet:
        print((ui or Translator()).t(
            "summary", board=v["BOARD_NAME"], part=v["PART"],
            ps=v["PS_AVAILABLE_BYTES"] // 2**20, pl=v["PL_RESERVED_MB"],
            id=v["CONFIG_ID"][:12],
        ))
    return v


def menu(k: kc.Kconfig, ui: Translator | None = None) -> bool:
    """Simple portable fallback editor; the installed CLI can wrap this model."""
    ui = ui or Translator()
    node, stack = k.top_node, []
    while True:
        print("\n" + (ui.prompt(node.prompt[0]) if node.prompt else ui.t("menu_title")))
        entries, child = [], node.list
        while child:
            if child.prompt and kc.expr_value(child.prompt[1]):
                entries.append(child)
            child = child.next
        for index, entry in enumerate(entries, 1):
            item = entry.item
            if isinstance(item, kc.Choice):
                state = f"({item.selection.name if item.selection else '-'}) >"
            elif isinstance(item, kc.Symbol):
                state = f"[{item.str_value}]"
            else:
                state = ">" if entry.list else ""
            name = f" ({item.name})" if isinstance(item, (kc.Symbol, kc.Choice)) and item.name else ""
            print(f" {index:2}: {ui.prompt(entry.prompt[0])}{name} {state}")
        command = input(ui.t("menu_input")).strip().lower()
        if command in ("q", "quit", "放弃", "退出"):
            return False
        if command in ("l", "lang", "语言"):
            ui.cycle()
            continue
        if command in ("s", "save", "保存"):
            values(k)
            return True
        if command in ("b", "back", "返回"):
            if stack:
                node = stack.pop()
            continue
        if not command.isdigit() or not 1 <= int(command) <= len(entries):
            continue
        entry = entries[int(command) - 1]
        if entry.list:
            stack.append(node)
            node = entry
            continue
        item = entry.item
        if not isinstance(item, kc.Symbol):
            continue
        if item.type == kc.BOOL:
            item.set_value(2 if item.tri_value == 0 or item.choice else 0)
            if item.choice and stack:
                node = stack.pop()
        else:
            new_value = input(ui.t("menu_value", name=item.name, value=item.str_value)).strip()
            if new_value and not item.set_value(new_value):
                print(ui.t("invalid_value_simple"))
