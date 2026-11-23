"""A keyboard and mouse driven, full-screen Kconfig editor for any board model."""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option


class ConfigSession:
    """Keep edits in memory, with rollback on validation errors and explicit save."""

    def __init__(self, model, k, target: Path, out: Path, ui):
        self.model, self.k, self.target, self.out, self.ui = model, k, target, out, ui
        self.saved_id = model.values(k)["CONFIG_ID"]
        self.history = []

    @property
    def dirty(self):
        return self.model.values(self.k)["CONFIG_ID"] != self.saved_id

    def snapshot(self):
        return (self.k, [(s, s.user_value) for s in self.k.unique_defined_syms],
                [(c, c.user_value, c.user_selection) for c in self.k.unique_choices])

    def restore(self, state):
        self.k, symbols, choices = state
        self.k.unset_values()
        for s, value in symbols:
            if value is not None:
                s.set_value(value)
        for c, value, selected in choices:
            if value is not None:
                c.set_value(value)
            if selected is not None:
                selected.set_value(2)

    def change(self, name, value):
        before = self.snapshot()
        try:
            self.model.set_values(self.k, [f"{name}={value}"])
        except ValueError:
            self.restore(before)
            raise
        self.history.append(before)

    def profile(self, name):
        candidate = self.model.load_config(self.model.ROOT / "configs" / f"{name}_defconfig")
        self.model.values(candidate)
        self.history.append(self.snapshot())
        self.k = candidate

    def undo(self):
        if self.history:
            self.restore(self.history.pop())

    def save(self):
        result = self.model.generate(self.k, self.out, config_path=self.target, quiet=True)
        self.saved_id = result["CONFIG_ID"]
        return result


class MessageDialog(ModalScreen):
    BINDINGS = [("escape", "dismiss(None)", "")]

    def __init__(self, title, message, ui):
        super().__init__()
        self.heading, self.message, self.ui = title, message, ui

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self.heading, classes="dialog-title", markup=False)
            with VerticalScroll(classes="dialog-body"):
                yield Static(self.message, markup=False)
            yield Button(self.ui.t("tui_ok"), id="ok", variant="primary")

    def on_mount(self):
        self.query_one(Button).focus()

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(None)


class EditInput(Input):
    # Windows/Linux users can use the familiar select-all shortcut.
    BINDINGS = [Binding("ctrl+a", "select_all", show=False)]


class ValueDialog(ModalScreen):
    BINDINGS = [("escape", "dismiss(None)", "")]

    def __init__(self, title, value, hint, ui, *, integer=False):
        super().__init__()
        self.heading, self.value, self.hint, self.ui, self.integer = title, value, hint, ui, integer

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self.heading, classes="dialog-title", markup=False)
            yield Static(self.hint, classes="dialog-hint", markup=False)
            yield EditInput(self.value, id="value", type="integer" if self.integer else "text")
            with Horizontal(classes="dialog-actions"):
                yield Button(self.ui.t("tui_apply"), id="apply", variant="primary")
                yield Button(self.ui.t("tui_cancel"), id="cancel")

    def on_mount(self):
        field = self.query_one(Input)
        field.focus()
        field.action_select_all()

    def on_input_submitted(self, event: Input.Submitted):
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(self.query_one(Input).value if event.button.id == "apply" else None)


class ProfileDialog(ModalScreen):
    BINDINGS = [("escape", "dismiss(None)", "")]

    def __init__(self, profiles, ui):
        super().__init__()
        self.profiles, self.ui = profiles, ui

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self.ui.t("tui_profiles"), classes="dialog-title", markup=False)
            yield Static(self.ui.t("tui_profiles_hint"), classes="dialog-hint", markup=False)
            yield OptionList(*(Option(p, id=p) for p in self.profiles), id="profiles")
            yield Button(self.ui.t("tui_cancel"), id="cancel")

    def on_mount(self):
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.dismiss(event.option.id)

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(None)


class ExitDialog(ModalScreen):
    BINDINGS = [("escape", "dismiss('cancel')", "")]

    def __init__(self, ui):
        super().__init__()
        self.ui = ui

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self.ui.t("tui_unsaved"), classes="dialog-title", markup=False)
            yield Static(self.ui.t("tui_exit_hint"), classes="dialog-hint", markup=False)
            with Horizontal(classes="dialog-actions"):
                yield Button(self.ui.t("tui_save_exit"), id="save", variant="primary")
                yield Button(self.ui.t("tui_discard"), id="discard", variant="error")
                yield Button(self.ui.t("tui_cancel"), id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id)


class ConfigApp(App[int]):
    """Blue menuconfig-style UI. No hardware commands are run by this app."""

    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: #071b45; color: #e6efff; }
    #banner { height: 3; background: #104a96; padding: 1 2; text-style: bold; color: #ffffff; }
    #memory { height: 3; padding: 1 2; background: #0b2e63; color: #a8ddff; }
    #crumb { height: 2; padding: 0 2; color: #ffdf7e; content-align: left middle; }
    #body { height: 1fr; margin: 0 2; }
    #options { width: 3fr; height: 1fr; border: double #86b7f6; background: #0a2352; padding: 0 1; }
    #options:focus { border: double #d7eaff; }
    OptionList > .option-list--option { padding: 0 1; }
    OptionList > .option-list--option-highlighted { background: #1e60a9; color: #ffffff; text-style: bold; }
    #details-wrap { width: 2fr; height: 1fr; margin-left: 1; padding: 1 2; border: solid #3868a8; background: #0a2352; }
    #details { height: auto; }
    #status { height: 2; padding: 0 2; content-align: left middle; color: #ffdf7e; }
    #actions { height: 3; padding: 0 2; background: #0b2e63; }
    #actions Button { margin-right: 1; min-width: 10; width: 1fr; height: 3; border: none; background: #174b8b; color: #ffffff; }
    #actions Button:focus { background: #2a73c4; text-style: bold; }
    #keys { height: 2; padding: 0 2; content-align: left middle; color: #b2c7e5; }
    .compact #details-wrap { display: none; }
    .compact #banner { height: 2; padding: 0 1; content-align: left middle; }
    .compact #memory { height: 2; padding: 0 1; content-align: left middle; }
    .compact #keys { height: 1; }
    .compact #body { margin: 0 1; }
    ModalScreen { align: center middle; background: #00000088; }
    .dialog { width: 72; max-width: 95%; height: auto; max-height: 85%; background: #10366c; border: double #bddbff; padding: 1 2; }
    .dialog-title { color: #ffdf7e; text-style: bold; height: auto; margin-bottom: 1; }
    .dialog-hint { height: auto; margin-bottom: 1; }
    .dialog-body { height: auto; max-height: 16; margin-bottom: 1; }
    .dialog-actions { height: auto; margin-top: 1; }
    .dialog Button { margin-right: 1; min-width: 10; width: auto; }
    .dialog Input { background: #071b45; border: tall #86b7f6; }
    #profiles { height: auto; max-height: 12; background: #0a2352; margin-bottom: 1; }
    """
    BINDINGS = [
        Binding("space", "toggle", show=False), Binding("y", "set_bool(True)", show=False),
        Binding("n", "set_bool(False)", show=False), Binding("right", "open", show=False),
        Binding("escape,backspace,left", "back", show=False),
        Binding("slash,ctrl+f", "search", show=False), Binding("f1,question_mark", "help", show=False),
        Binding("f2,ctrl+s", "save", show=False), Binding("f3", "profiles", show=False),
        Binding("f4", "language", show=False), Binding("ctrl+z", "undo", show=False),
        Binding("f10,ctrl+q,q", "request_quit", show=False),
    ]

    def __init__(self, session: ConfigSession):
        super().__init__()
        self.session = session
        self.ui, self.model = session.ui, session.model
        self.node = session.k.top_node
        self.parents = []
        self.entries = []
        self.entry_depths = {}
        self.details_text = ""
        self.search_query = ""
        self.notice = ""

    def compose(self) -> ComposeResult:
        yield Static(id="banner", markup=False)
        yield Static(id="memory", markup=False)
        yield Static(id="crumb", markup=False)
        with Horizontal(id="body"):
            yield OptionList(id="options")
            with VerticalScroll(id="details-wrap"):
                yield Static(id="details", markup=False)
        yield Static(id="status", markup=False)
        with Horizontal(id="actions"):
            yield Button(id="save")
            yield Button(id="profiles")
            yield Button(id="language")
            yield Button(id="exit")
        yield Static(id="keys", markup=False)

    def on_mount(self):
        self.theme = "textual-dark"
        self.rebuild()
        self.query_one("#options", OptionList).focus()

    def on_resize(self, event):
        self.screen_stack[0].set_class(event.size.width < 100 or event.size.height < 28, "compact")

    def check_action(self, action, parameters):
        # A dialog owns keyboard input until it is accepted or cancelled.
        return not isinstance(self.screen, ModalScreen)

    def label(self, node):
        item, kc = node.item, self.model.kc
        prompt = self.ui.prompt(node.prompt[0])
        indent = "  " * self.entry_depths.get(id(node), 0)
        if isinstance(item, kc.Symbol):
            if item.type == kc.BOOL:
                mark = "(*)" if item.tri_value == 2 else "( )" if item.choice else "[ ]"
                if not item.choice:
                    mark = "[*]" if item.tri_value == 2 else "[ ]"
                if not item.visibility:
                    mark = "-*-" if item.tri_value == 2 else "- -"
            else:
                mark = f"({item.str_value})"
            return Text(f"{indent}{mark}  {prompt}", style="dim" if not item.visibility else "")
        if isinstance(item, kc.Choice):
            selected = item.selection
            value = self.ui.prompt(selected.nodes[0].prompt[0]) if selected else "-"
            return Text(f"---> {prompt}  ({value})", style="bold")
        if node.list:
            return Text(f"---> {prompt}", style="bold")
        return Text(f"     {prompt}", style="dim")

    def rebuild(self, selected=None):
        k, kc = self.session.k, self.model.kc
        self.entries = []
        self.entry_depths = {}
        if self.search_query:
            from .cli import option_rows
            names = {r["name"] for r in option_rows(self.model, k, self.ui)
                     if self.search_query.casefold() in r["_search"].casefold() and not r["fixed"]}
            self.entries = [next(n for n in k.syms[name].nodes if n.prompt) for name in names]
            self.entries.sort(key=lambda n: n.item.name)
        else:
            def walk(child, depth=0):
                while child:
                    # Kconfig makes dependent flags implicit children of their
                    # parent symbol. Show them inline, including unavailable ones.
                    if child.prompt:
                        self.entries.append(child)
                        self.entry_depths[id(child)] = depth
                    if isinstance(child.item, kc.Symbol) and child.list:
                        walk(child.list, depth + 1)
                    child = child.next
            walk(self.node.list)
        widget = self.query_one("#options", OptionList)
        old = widget.highlighted or 0
        widget.clear_options()
        widget.add_options([Option(self.label(n)) for n in self.entries])
        index = next((i for i, n in enumerate(self.entries) if n.item is selected), min(old, len(self.entries) - 1))
        widget.highlighted = max(0, index) if self.entries else None
        v = self.model.values(k)
        self.title = f"{v['BOARD_NAME']} · {self.ui.t('tui_title')}"
        self.query_one("#banner", Static).update(self.title + ("  *" if self.session.dirty else ""))
        self.query_one("#memory", Static).update(self.ui.t("tui_memory", total=v["DDR_TOTAL_BYTES"] // 2**20,
            ps=v["PS_AVAILABLE_BYTES"] // 2**20, pl=v["PL_RESERVED_MB"], clock=v["PL_CLOCK_MHZ"]))
        path = [n.prompt[0] for n, _ in self.parents] + [self.node.prompt[0]]
        self.query_one("#crumb", Static).update(self.ui.t("tui_search_results", query=self.search_query)
            if self.search_query else "  /  ".join(self.ui.prompt(p) for p in path[1:]) or self.ui.t("tui_root"))
        for name in ("save", "profiles", "language", "exit"):
            self.query_one(f"#{name}", Button).label = self.ui.t(f"tui_button_{name}")
        self.query_one("#keys", Static).update(self.ui.t("tui_keys"))
        state = self.ui.t("tui_dirty") if self.session.dirty else self.ui.t("tui_clean")
        self.query_one("#status", Static).update(self.notice or state)
        self.show_details()

    def current(self):
        index = self.query_one("#options", OptionList).highlighted
        return self.entries[index] if index is not None and index < len(self.entries) else None

    def show_details(self):
        node = self.current()
        text = self.ui.t("no_results")
        if node:
            s, kc = node.item, self.model.kc
            text = self.ui.prompt(node.prompt[0]) + "\n\n"
            if isinstance(s, kc.Symbol):
                text += f"CONFIG_{s.name}={s.str_value}\n\n"
                text += f"{self.ui.t('dependency')}: {kc.expr_str(s.direct_dep)}\n"
                for low, high, condition in s.ranges:
                    if kc.expr_value(condition):
                        text += f"{self.ui.t('range')}: {low.str_value}..{high.str_value}\n"
                        break
                if not s.visibility:
                    text += self.ui.t("unavailable") + "\n"
                if node.help:
                    text += "\n" + self.ui.help(s.name, node.help) + "\n"
            text += "\n" + self.ui.t("tui_detail_hint")
        self.details_text = text
        self.query_one("#details", Static).update(text)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        if event.option_list.id == "options":
            self.show_details()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if event.option_list.id == "options":
            self.action_open()

    def on_button_pressed(self, event: Button.Pressed):
        action = {"save": self.action_save, "profiles": self.action_profiles,
                  "language": self.action_language, "exit": self.action_request_quit}.get(event.button.id)
        if action:
            action()

    def action_open(self):
        node = self.current()
        if not node:
            return
        s, kc = node.item, self.model.kc
        if node.list and not isinstance(s, kc.Symbol):
            self.parents.append((self.node, s))
            self.node = node
            self.notice = ""
            self.rebuild()
            self.query_one("#options", OptionList).highlighted = 0
        elif isinstance(s, kc.Symbol):
            if s.type == kc.BOOL:
                self.action_toggle()
            else:
                if not s.visibility:
                    self.action_help()
                    return
                hint = self.ui.help(s.name, node.help) if node.help else self.ui.prompt(node.prompt[0])
                active = next(((l.str_value, h.str_value) for l, h, c in s.ranges if kc.expr_value(c)), None)
                if active:
                    hint += f"\n{self.ui.t('range')}: {active[0]}..{active[1]}"
                self.push_screen(ValueDialog(s.name, s.str_value, hint, self.ui, integer=s.type == kc.INT),
                                 lambda value: self.change(s.name, value) if value is not None else None)
        else:
            self.action_help()

    def change(self, name, value):
        try:
            self.session.change(name, value)
        except ValueError as error:
            self.push_screen(MessageDialog(self.ui.t("error"), self.ui.error(error), self.ui))
        else:
            self.notice = ""
        self.rebuild(self.session.k.syms[name])

    def action_toggle(self):
        node = self.current()
        if node and isinstance(node.item, self.model.kc.Symbol):
            s = node.item
            if s.type == self.model.kc.BOOL:
                self.change(s.name, "y" if not s.tri_value or s.choice else "n")
            else:
                self.action_open()
        elif node:
            self.action_open()

    def action_set_bool(self, enabled):
        node = self.current()
        if node and isinstance(node.item, self.model.kc.Symbol) and node.item.type == self.model.kc.BOOL:
            self.change(node.item.name, "y" if enabled else "n")

    def action_back(self):
        self.notice = ""
        if self.search_query:
            self.search_query = ""
            self.rebuild()
        elif self.parents:
            self.node, selected = self.parents.pop()
            self.rebuild(selected)
        else:
            self.action_request_quit()

    def action_save(self):
        try:
            self.session.save()
        except (ValueError, OSError) as error:
            self.push_screen(MessageDialog(self.ui.t("error"), self.ui.error(error), self.ui))
            return False
        self.notice = self.ui.t("saved", path=self.session.target)
        self.rebuild()
        return True

    def action_search(self):
        def searched(value):
            if value is not None:
                self.search_query = value.strip()
                self.notice = ""
                self.rebuild()
                self.query_one("#options", OptionList).focus()
        self.push_screen(ValueDialog(self.ui.t("tui_search"), self.search_query,
                                     self.ui.t("tui_search_hint"), self.ui), searched)

    def action_profiles(self):
        profiles = sorted(p.name.removesuffix("_defconfig") for p in (self.model.ROOT / "configs").glob("*_defconfig"))
        def loaded(name):
            if name is not None:
                try:
                    self.session.profile(name)
                except (ValueError, OSError) as error:
                    self.push_screen(MessageDialog(self.ui.t("error"), self.ui.error(error), self.ui))
                    return
                self.reset_navigation()
                self.notice = self.ui.t("tui_profile_loaded", name=name)
                self.rebuild()
        self.push_screen(ProfileDialog(profiles, self.ui), loaded)

    def reset_navigation(self):
        self.node, self.parents, self.search_query = self.session.k.top_node, [], ""

    def action_undo(self):
        self.session.undo()
        self.reset_navigation()
        self.notice = ""
        self.rebuild()

    def action_language(self):
        self.ui.cycle()
        self.notice = ""
        self.rebuild()

    def action_help(self):
        node = self.current()
        title = self.ui.prompt(node.prompt[0]) if node else self.ui.t("tui_title")
        self.push_screen(MessageDialog(title, self.details_text, self.ui))

    def action_request_quit(self):
        if not self.session.dirty:
            self.exit(0)
            return
        def decided(choice):
            if choice == "discard" or (choice == "save" and self.action_save()):
                self.exit(0)
        self.push_screen(ExitDialog(self.ui), decided)


def run_tui(model, k, target, out, ui):
    return ConfigApp(ConfigSession(model, k, target, out, ui)).run() or 0
