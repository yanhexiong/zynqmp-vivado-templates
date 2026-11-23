"""Command-line configuration editing; hardware initialization stays in Tcl."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

from .i18n import ConfigError, Translator, resolve_language


class HelpFormatter(argparse.HelpFormatter):
    def __init__(self, prog, ui):
        super().__init__(prog)
        self.ui = ui

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or self.ui.t("usage") + ": ")


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, ui, **kwargs):
        self.ui = ui
        kwargs.update(add_help=False, formatter_class=lambda prog: HelpFormatter(prog, ui))
        super().__init__(*args, **kwargs)
        self._positionals.title = ui.t("commands")
        self._optionals.title = ui.t("options")
        self.add_argument("-h", "--help", action="help", help=ui.t("help"))

    def error(self, message):
        localized = None
        for pattern, key in [
            (r"unrecognized arguments: (.*)", "parse_unknown"),
            (r"the following arguments are required: (.*)", "parse_required"),
        ]:
            if m := re.fullmatch(pattern, message):
                localized = self.ui.t(key, detail=m[1])
                break
        if m := re.fullmatch(r"argument (.*): invalid choice: (.*?) \(choose from (.*)\)", message):
            localized = self.ui.t("parse_choice", argument=m[1], value=m[2], choices=m[3])
        for suffix, key in [("expected one argument", "parse_one"), ("expected at least one argument", "parse_many")]:
            if message.startswith("argument ") and message.endswith(": " + suffix):
                localized = self.ui.t(key, argument=message[len("argument "):-len(": " + suffix)])
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.ui.t('error')}: {localized or self.ui.t('parse_error', detail=message)}\n")


def make_parser(ui: Translator) -> ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--lang", choices=["auto", "zh", "en", "both"], default=argparse.SUPPRESS, help=ui.t("lang_help"))
    common.add_argument("--template", type=Path, default=argparse.SUPPRESS, help=ui.t("template_help"))
    common.add_argument("--config", type=Path, default=argparse.SUPPRESS, help=ui.t("config_help"))
    common.add_argument("--out", type=Path, default=argparse.SUPPRESS, help=ui.t("out_help"))
    common.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS, help=ui.t("quiet_help"))
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=ui.t("json_help"))
    p = ArgumentParser(prog="fz5-config", ui=ui, parents=[common], description=ui.t("description"))
    p.add_argument("--version", action="version", version="fz5-config 0.3.0", help=ui.t("version_help"))
    commands = p.add_subparsers(dest="command", title=ui.t("commands"), metavar="COMMAND", parser_class=lambda **kwargs: ArgumentParser(ui=ui, **kwargs))

    def command(name, help_key, aliases=()):
        parser = commands.add_parser(name, parents=[common], help=ui.t(help_key), description=ui.t(help_key), aliases=list(aliases))
        parser.set_defaults(command=name)
        return parser

    command("menu", "menu_help", ["menuconfig"])
    command("list", "list_help", ["show"])
    command("get", "get_help").add_argument("symbols", nargs="+", metavar="SYMBOL", help=ui.t("symbols_help"))
    command("set", "set_help").add_argument("assignments", nargs="+", metavar="SYMBOL=VALUE", help=ui.t("assignments_help"))
    for name in ("enable", "disable"):
        command(name, name + "_help").add_argument("symbols", nargs="+", metavar="SYMBOL", help=ui.t("symbols_help"))
    command("search", "search_help").add_argument("query", help=ui.t("query_help"))
    command("describe", "describe_help").add_argument("symbol", metavar="SYMBOL", help=ui.t("symbols_help"))
    command("profiles", "profiles_help")
    command("defconfig", "defconfig_help").add_argument("--profile", default="fz5d", help=ui.t("profile_help"))
    command("generate", "generate_help")
    command("validate", "validate_help")
    return p


def template_root(explicit: Path | None = None) -> Path:
    def valid(path):
        return (path / "Kconfig").is_file() and (path / "scripts/configure.py").is_file()

    configured = explicit or os.environ.get("FZ5_TEMPLATE_ROOT")
    if configured:
        root = Path(configured).resolve()
        if not valid(root):
            raise ConfigError("invalid_template", path=root)
        return root
    current = Path.cwd()
    for root in (current, *current.parents, Path(__file__).resolve().parents[1]):
        if valid(root):
            return root
    raise ConfigError("template_missing")


def load_model(root: Path):
    spec = importlib.util.spec_from_file_location("_fz5_template_model", root / "scripts/configure.py")
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    return model


def normalized(name: str) -> str:
    return name.removeprefix("CONFIG_")


def display_value(value) -> str:
    return ("y" if value else "n") if isinstance(value, bool) else str(value)


def option_rows(model, k, ui):
    result = []
    for s in k.unique_defined_syms:
        node = next((n for n in s.nodes if n.prompt), s.nodes[0])
        prompt = node.prompt[0] if node.prompt else s.name
        fixed = not any(n.prompt for n in s.nodes)
        value = s.tri_value == 2 if s.type == model.kc.BOOL else int(s.str_value) if s.type == model.kc.INT else s.str_value
        active_range = next(({"min": int(low.str_value), "max": int(high.str_value)} for low, high, condition in s.ranges if model.kc.expr_value(condition)), None)
        result.append({
            "name": s.name,
            "value": value,
            "type": model.kc.TYPE_TO_STR[s.type],
            "range": active_range,
            "description": ui.prompt(prompt),
            "help": ui.help(s.name, node.help) if node.help else "",
            "dependency": model.kc.expr_str(s.direct_dep),
            "available": bool(s.visibility),
            "fixed": fixed,
            "_search": " ".join((s.name, prompt, Translator("en").prompt(prompt), Translator("zh").prompt(prompt), Translator("en").help(s.name, node.help or ""), Translator("zh").help(s.name, node.help or ""))),
        })
    return result


def public_row(row):
    return {name: value for name, value in row.items() if not name.startswith("_")}


def print_json(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def print_rows(rows, ui):
    if not rows:
        print(ui.t("no_results"))
        return
    print(f"{ui.t('symbol_column'):<26} {ui.t('value_column'):<8} {ui.t('description_column')}")
    for row in rows:
        state = ui.t("fixed") if row["fixed"] else ui.t("unavailable") if not row["available"] else ""
        label = row["description"] + (f" [{state}]" if state else "")
        print(f"{row['name']:<26} {display_value(row['value']):<8} {label}")


def main(argv=None, *, default_menu=False) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    requested_language = None
    for i, word in enumerate(argv):
        if word.startswith("--lang="):
            requested_language = word.partition("=")[2]
        elif word == "--lang" and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            requested_language = argv[i + 1]
    try:
        ui = Translator(resolve_language(requested_language))
    except ValueError:
        if requested_language is None:
            raise
        ui = Translator("en")  # argparse will report the invalid --lang value.
    parser = make_parser(ui)
    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "menu"
    try:
        return execute(args, ui)
    except (ValueError, OSError) as error:
        print(f"{ui.t('error')}: {ui.error(error)}", file=sys.stderr)
        return 1
    except EOFError:
        print(ui.t("input_ended"))
        return 0
    except KeyboardInterrupt:
        print(ui.t("cancelled"), file=sys.stderr)
        return 130


def execute(args, ui):
    root = template_root(getattr(args, "template", None))
    profiles = sorted(p.name.removesuffix("_defconfig") for p in (root / "configs").glob("*_defconfig"))
    if args.command == "profiles":
        print_json(profiles) if getattr(args, "json", False) else print("\n".join(profiles))
        return 0
    model = load_model(root)
    source = getattr(args, "config", None)
    target = (source or root / ".config").resolve()
    out = getattr(args, "out", root / "generated").resolve()
    as_json, quiet = getattr(args, "json", False), getattr(args, "quiet", False)
    if args.command == "defconfig":
        if args.profile not in profiles:
            raise ConfigError("profile_missing", name=args.profile)
        source = root / "configs" / f"{args.profile}_defconfig"
    try:
        k = model.load_config(source)
    except model.kc.KconfigError as error:
        raise ConfigError("config_warning", detail=str(error)) from None
    v = model.values(k)
    if args.command in ("list", "search", "describe"):
        rows = option_rows(model, k, ui)
        if args.command == "list":
            print_json(v) if as_json else print_rows(rows, ui)
        elif args.command == "search":
            rows = [r for r in rows if args.query.casefold() in r["_search"].casefold()]
            print_json([public_row(r) for r in rows]) if as_json else print_rows(rows, ui)
        else:
            name = normalized(args.symbol)
            row = next((r for r in rows if r["name"] == name), None)
            if row is None:
                raise ConfigError("unknown_symbol", name=name)
            if as_json:
                print_json(public_row(row))
            else:
                print(f"{name}={display_value(row['value'])}\n{row['description']}")
                print(f"{ui.t('type')}: {row['type']}\n{ui.t('dependency')}: {row['dependency']}")
                if row["range"] is not None:
                    print(f"{ui.t('range')}: {row['range']['min']}..{row['range']['max']}")
                state = "fixed" if row["fixed"] else "available" if row["available"] else "unavailable"
                print(f"{ui.t('state')}: {ui.t(state)}")
                if row["help"]:
                    print(row["help"])
        return 0
    if args.command == "get":
        selected = {}
        for symbol in args.symbols:
            # CONFIG_ID is itself a canonical derived key, not an alias for ID.
            name = symbol if symbol in v else normalized(symbol)
            if name not in v:
                raise ConfigError("unknown_symbol", name=name)
            selected[name] = v[name]
        if as_json:
            print_json(selected)
        elif len(selected) == 1:
            print(display_value(next(iter(selected.values()))))
        else:
            for name, value in selected.items():
                print(f"{name}={display_value(value)}")
        return 0
    if args.command == "validate":
        print_json({"valid": True, "config_id": v["CONFIG_ID"]}) if as_json else print(ui.t("valid", board=v["BOARD_NAME"], id=v["CONFIG_ID"][:12]))
        return 0
    if args.command == "menu":
        if as_json:
            raise ConfigError("interactive_json")
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ConfigError("terminal_required")
        from .tui import run_tui
        return run_tui(model, k, target, out, ui)
    if args.command == "set":
        model.set_values(k, args.assignments)
    elif args.command in ("enable", "disable"):
        assignments = []
        for symbol in args.symbols:
            name = normalized(symbol)
            if name not in k.syms or not k.syms[name].nodes:
                raise ConfigError("unknown_symbol", name=name)
            if k.syms[name].type != model.kc.BOOL:
                raise ConfigError("bool_only", name=name)
            assignments.append(f"{name}={'y' if args.command == 'enable' else 'n'}")
        model.set_values(k, assignments)
    v = model.generate(k, out, config_path=target, ui=ui, quiet=quiet or as_json)
    if as_json:
        print_json(v)
    elif not quiet:
        print(ui.t("saved", path=target))
        print(ui.t("vivado_input", path=out / "config.tcl"))
    return 0


def entrypoint(*, default_menu=False):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        raise SystemExit(main(default_menu=default_menu))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)
