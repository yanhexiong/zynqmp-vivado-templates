"""Exercise the real terminal UI with Textual's keyboard/mouse driver."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from textual.widgets import Input, OptionList, Static

from fz5_config.cli import load_model, main
from fz5_config.i18n import Translator
from fz5_config.tui import ConfigApp, ConfigSession, ExitDialog, MessageDialog, ProfileDialog, ValueDialog

ROOT = Path(__file__).resolve().parents[1]


class TerminalUI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="FZ5 TUI 用户 ")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "custom board.config"
        self.out = Path(self.temp.name) / "generated files"
        self.model = load_model(ROOT)
        k = self.model.load_config(ROOT / "configs/fz5d_defconfig")
        self.model.generate(k, self.out, config_path=self.target, quiet=True)
        self.session = ConfigSession(self.model, k, self.target, self.out, Translator("zh"))
        self.app = ConfigApp(self.session)

    def files(self):
        return {p.name: p.read_bytes() for p in [self.target, *self.out.glob("*")]}

    async def test_keyboard_edits_memory_and_explicit_save_keeps_editor_open(self):
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("enter", "down", "down", "enter")
            self.assertIsInstance(self.app.screen, ValueDialog)
            await pilot.press("ctrl+a", "2", "0", "4", "8", "enter")
            self.assertTrue(self.session.dirty)
            self.assertIn("PL 2048 MiB", str(self.app.query_one("#memory", Static).render()))
            self.assertEqual(json.loads((self.out / "config.json").read_text())["PL_RESERVED_MB"], 1024)
            await pilot.press("f2")
            self.assertFalse(self.session.dirty)
            self.assertEqual(json.loads((self.out / "config.json").read_text())["PL_RESERVED_MB"], 2048)
            self.assertIn("CONFIG_PL_RESERVED_MB=2048", self.target.read_text())
            self.assertEqual(self.app.screen.id, "_default")

    async def test_invalid_alignment_rolls_back_and_never_writes(self):
        before = self.files()
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("enter", "down", "down", "enter")
            await pilot.press("ctrl+a", "6", "5", "enter")
            self.assertIsInstance(self.app.screen, MessageDialog)
            self.assertEqual(self.model.values(self.session.k)["PL_RESERVED_MB"], 1024)
            self.assertFalse(self.session.dirty)
            self.assertEqual(self.files(), before)
            await pilot.press("escape")

    async def test_space_toggles_and_exit_cancel_then_discard_preserves_disk(self):
        before = self.files()
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("down", "enter", "down", "space")
            self.assertFalse(self.session.k.syms["PS_UART1"].tri_value)
            self.assertTrue(self.session.dirty)
            await pilot.press("f10")
            self.assertIsInstance(self.app.screen, ExitDialog)
            await pilot.click("#cancel")
            self.assertTrue(self.session.dirty)
            await pilot.press("f10")
            await pilot.click("#discard")
            self.assertEqual(self.files(), before)

    async def test_save_and_exit_commits_changes(self):
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("down", "enter", "down", "space", "f10")
            await pilot.click("#save")
            self.assertFalse(json.loads((self.out / "config.json").read_text())["PS_UART1"])

    async def test_unavailable_dependency_remains_visible_and_cannot_be_enabled(self):
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("down", "enter")
            names = [getattr(n.item, "name", None) for n in self.app.entries]
            self.assertIn("PS_USB3", names)
            self.app.query_one("#options", OptionList).highlighted = names.index("PS_USB3")
            await pilot.press("space")
            self.assertIsInstance(self.app.screen, MessageDialog)
            self.assertFalse(self.session.k.syms["PS_USB3"].tri_value)
            await pilot.press("escape")
            self.assertFalse(self.session.dirty)

    async def test_search_chinese_then_help_and_return_to_menu(self):
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("slash")
            self.app.screen.query_one(Input).value = "隔离"
            await pilot.press("enter")
            self.assertEqual([n.item.name for n in self.app.entries], ["PL_RESERVED_MB"])
            await pilot.press("f1")
            self.assertIsInstance(self.app.screen, MessageDialog)
            await pilot.press("escape", "escape")
            self.assertFalse(self.app.search_query)
            self.assertEqual(len(self.app.entries), 3)

    async def test_language_switch_preserves_selection_and_all_generated_bytes(self):
        before = self.files()
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("down", "enter", "down")
            selected = self.app.current().item.name
            await pilot.press("f4")
            self.assertEqual(self.session.ui.language, "both")
            self.assertEqual(self.app.current().item.name, selected)
            await pilot.press("f4", "f2")
            self.assertEqual(self.session.ui.language, "en")
            self.assertEqual(self.files(), before)

    async def test_profiles_load_in_memory_and_undo_restores_before_profile(self):
        before = self.files()
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("f3")
            self.assertIsInstance(self.app.screen, ProfileDialog)
            listing = self.app.screen.query_one(OptionList)
            listing.highlighted = next(i for i in range(listing.option_count) if listing.get_option_at_index(i).id == "minimal")
            await pilot.press("enter")
            self.assertFalse(self.model.values(self.session.k)["PL_DMA"])
            self.assertTrue(self.session.dirty)
            self.assertEqual(self.files(), before)
            await pilot.press("ctrl+z")
            self.assertFalse(self.session.dirty)
            self.assertTrue(self.model.values(self.session.k)["PL_DMA"])

    async def test_choice_uses_radio_selection(self):
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("enter", "enter", "down", "space")
            self.assertTrue(self.session.k.syms["BOARD_FZ5C"].tri_value)
            self.assertFalse(self.session.k.syms["BOARD_FZ5D"].tri_value)
            self.assertEqual(self.model.values(self.session.k)["DDR_TOTAL_BYTES"], 4 * 2**30)

    async def test_small_terminal_can_edit_and_open_help(self):
        async with self.app.run_test(size=(80, 24)) as pilot:
            self.assertTrue(self.app.screen.has_class("compact"))
            await pilot.press("enter", "down", "down", "f1")
            self.assertIsInstance(self.app.screen, MessageDialog)
            await pilot.press("escape", "enter")
            self.assertIsInstance(self.app.screen, ValueDialog)


class EntryPoint(unittest.TestCase):
    def test_no_command_launches_full_screen_editor(self):
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), patch("fz5_config.tui.run_tui", return_value=0) as launch:
            self.assertEqual(main(["--template", str(ROOT)]), 0)
            launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
