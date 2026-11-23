"""AXU4EV board contracts and real full-screen editor interactions."""
import json
from pathlib import Path
from string import Formatter
import tempfile
import unittest

from textual.widgets import Input, OptionList
from axu4ev_config.cli import load_model
from axu4ev_config.i18n import Translator, catalog
from axu4ev_config.tui import ConfigApp, ConfigSession, ExitDialog, MessageDialog

ROOT = Path(__file__).resolve().parents[1]


class Configuration(unittest.TestCase):
    def setUp(self):
        self.model = load_model(ROOT)
        self.k = self.model.load_config(ROOT / "configs/axu4ev_defconfig")

    def test_physical_ddr_and_default_pool(self):
        v = self.model.values(self.k)
        self.assertEqual(v["PART"], "xczu4ev-sfvc784-2-i")
        self.assertEqual(v["DDR_TOTAL_BYTES"], 4 * 2**30)
        self.assertEqual(v["DDR_HIGH_BASE"] + v["DDR_HIGH_SIZE"] - 1, 0x87fffffff)
        self.assertEqual(v["PL_POOL_BASE"], 0x840000000)
        self.assertEqual(v["PS_AVAILABLE_BYTES"], 3 * 2**30)
        self.assertEqual(v["DDR_HIGH_AXI_APERTURE_SIZE"], 32 * 2**30)

    def test_range_alignment_and_dependencies_are_rejected(self):
        for assignment in ("PL_RESERVED_MB=2112", "PL_RESERVED_MB=65"):
            k = self.model.load_config(ROOT / "configs/axu4ev_defconfig")
            with self.assertRaises(ValueError):
                self.model.set_values(k, [assignment])
        self.model.set_values(self.k, ["PS_USB0=n"])
        with self.assertRaises(ValueError):
            self.model.set_values(self.k, ["PS_USB3=y"])

    def test_zero_pool_removes_dma(self):
        self.model.set_values(self.k, ["PL_RESERVED_MB=0"])
        v = self.model.values(self.k)
        self.assertEqual(v["PL_POOL_BASE"], 0)
        self.assertFalse(v["PL_DMA"])

    def test_translation_coverage_and_format_fields(self):
        en, zh = catalog("en"), catalog("zh")
        for section in en:
            self.assertEqual(en[section].keys(), zh[section].keys())
            for key, text in en[section].items():
                fields = lambda s: {n for _, n, _, _ in Formatter().parse(s) if n}
                self.assertEqual(fields(text), fields(zh[section][key]))
        for node in [self.k.top_node, *self.k.node_iter()]:
            if node.prompt:
                self.assertIn(node.prompt[0], zh["prompts"])
            if getattr(node, "help", None):
                self.assertIn(node.item.name, zh["help"])


class TerminalUI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="AXU TUI 用户 ")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "board.config"
        self.out = Path(self.temp.name) / "output files"
        self.model = load_model(ROOT)
        k = self.model.load_config(ROOT / "configs/axu4ev_defconfig")
        self.model.generate(k, self.out, config_path=self.target, quiet=True)
        self.session = ConfigSession(self.model, k, self.target, self.out, Translator("zh"))
        self.app = ConfigApp(self.session)

    def files(self):
        return {p.name: p.read_bytes() for p in [self.target, *self.out.glob("*")]}

    async def test_memory_edit_save_and_language_independence(self):
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("enter", "enter")
            await pilot.press("ctrl+a", "2", "0", "4", "8", "enter", "f2")
            self.assertFalse(self.session.dirty)
            v = json.loads((self.out / "config.json").read_text())
            self.assertEqual(v["PL_POOL_BASE"], 0x800000000)
            self.assertEqual(v["PS_AVAILABLE_BYTES"], 2 * 2**30)
            saved = self.files()
            for _ in range(2):
                await pilot.press("f4", "f2")
                self.assertEqual(self.files(), saved)

    async def test_disabled_usb3_explains_dependency_and_rolls_back(self):
        before = self.files()
        async with self.app.run_test(size=(120, 36)) as pilot:
            await pilot.press("down", "enter")
            listing = self.app.query_one("#options", OptionList)
            names = [getattr(n.item, "name", None) for n in self.app.entries]
            listing.highlighted = names.index("PS_USB0")
            await pilot.press("n")
            self.assertFalse(self.model.values(self.session.k)["PS_USB3"])
            listing.highlighted = names.index("PS_USB3")
            await pilot.press("y")
            self.assertIsInstance(self.app.screen, MessageDialog)
            await pilot.press("escape", "f10")
            self.assertIsInstance(self.app.screen, ExitDialog)
            await pilot.click("#discard")
            self.assertEqual(self.files(), before)

    async def test_chinese_search_and_help_in_small_terminal(self):
        async with self.app.run_test(size=(80, 24)) as pilot:
            self.assertTrue(self.app.screen.has_class("compact"))
            await pilot.press("slash")
            self.app.screen.query_one(Input).value = "EEPROM"
            await pilot.press("enter")
            self.assertEqual([n.item.name for n in self.app.entries], ["PS_I2C0"])
            await pilot.press("f1")
            self.assertIsInstance(self.app.screen, MessageDialog)
            await pilot.press("escape")


if __name__ == "__main__":
    unittest.main()
