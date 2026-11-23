"""Portable editor contracts: paths, rejected writes and the Tcl handoff."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from configure import generate, load_config, values

try:
    import tkinter
except ImportError:
    tkinter = None
else:
    try:
        tkinter.Tcl()
    except tkinter.TclError:
        tkinter = None


class EditorCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="FZ5 config paths ")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.input = self.work / "board [literal] $value 用户.config"
        self.out = self.work / "generated config"
        self.run_editor("defconfig")

    def run_editor(self, *args, success=True):
        r = subprocess.run([sys.executable, str(ROOT / "config.py"), "--lang", "en", "--config", str(self.input), "--out", str(self.out), *args], cwd=self.work, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if success:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        else:
            self.assertNotEqual(r.returncode, 0)
        return r

    def snapshot(self):
        return {p: p.read_bytes() for p in [self.input, *self.out.glob("*")] if p.is_file()}

    def test_configure_from_an_unrelated_working_directory(self):
        r = self.run_editor("show", "--json")
        self.assertEqual(json.loads(r.stdout)["PL_RESERVED_MB"], 1024)
        self.assertTrue((self.out / "config.tcl").is_file())

    def test_dependency_order_is_independent_of_assignment_order(self):
        self.run_editor("set", "PS_USB3=y", "PS_USB0=y", "PL_RESERVED_MB=2048")
        v = json.loads((self.out / "config.json").read_text())
        self.assertTrue(v["PS_USB3"])
        self.assertEqual(v["PS_AVAILABLE_BYTES"], 6 << 30)

    def test_invalid_batch_does_not_write_any_configuration(self):
        old = self.snapshot()
        self.run_editor("set", "BOARD_FZ5C=y", "PL_RESERVED_MB=6144", success=False)
        self.assertEqual(self.snapshot(), old)

    def test_unavailable_dependency_is_an_error(self):
        old = self.snapshot()
        r = self.run_editor("set", "PS_USB3=y", success=False)
        self.assertIn("dependency", r.stderr)
        self.assertEqual(self.snapshot(), old)

    def test_fixed_setting_and_unknown_symbol_are_rejected(self):
        old = self.snapshot()
        self.run_editor("set", "PS_UART0=n", success=False)
        self.run_editor("set", "NOT_A_PERIPHERAL=y", success=False)
        self.assertEqual(self.snapshot(), old)

    def test_default_entry_requires_an_interactive_terminal(self):
        old = self.snapshot()
        r = subprocess.run([sys.executable, str(ROOT / "config.py"), "--lang", "en", "--config", str(self.input), "--out", str(self.out)], input="q\n", cwd=self.work, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 1)
        self.assertIn("terminal", r.stderr)
        self.assertEqual(self.snapshot(), old)

    def test_scripted_editor_saves_the_memory_setting(self):
        # Interactive navigation/edit/save is tested with Textual's real Pilot.
        self.run_editor("set", "PL_RESERVED_MB=2048")
        v = json.loads((self.out / "config.json").read_text())
        self.assertEqual(v["PL_RESERVED_MB"], 2048)
        self.assertIn("CONFIG_PL_RESERVED_MB=2048", self.input.read_text())


@unittest.skipIf(tkinter is None, "Optional Tcl interpreter not installed; configuration editing needs no tkinter")
class TclHandoff(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="FZ5 Tcl path ")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.target = self.work / "literal [not a command] $variable.config"
        self.out = self.work / "generated config"
        self.k = load_config(ROOT / "configs/fz5d_defconfig")
        with redirect_stdout(io.StringIO()):
            generate(self.k, self.out, config_path=self.target)
        self.tcl = tkinter.Tcl()
        self.tcl.call("source", str(ROOT / "tcl/config_io.tcl"))

    def load(self, out=None, root=ROOT):
        return self.tcl.call("::fz5::load_configuration", str(out or self.out), str(root))

    def test_literal_path_and_all_values_survive_the_tcl_roundtrip(self):
        self.load()
        for key, expected in values(self.k).items():
            if isinstance(expected, bool):
                expected = int(expected)
            self.assertEqual(str(self.tcl.getvar(f"cfg({key})")), str(expected), key)

    def test_windows_crlf_and_bom_are_accepted_by_tcl(self):
        text = self.target.read_text(encoding="utf-8")
        self.target.write_bytes(b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8"))
        self.load()
        self.assertEqual(int(self.tcl.getvar("cfg(PL_RESERVED_MB)")), 1024)

    def test_stale_config_is_rejected_before_initialization(self):
        text = self.target.read_text().replace("CONFIG_PL_RESERVED_MB=1024", "CONFIG_PL_RESERVED_MB=2048")
        self.target.write_text(text)
        with self.assertRaisesRegex(tkinter.TclError, "Configuration changed"):
            self.load()

    def test_default_handoff_survives_moving_the_template_tree(self):
        # Default handoff points to '.config' relative to the template, not D:/...
        moved = self.work / "moved project with spaces"
        moved.mkdir()
        shutil.copy2(ROOT / ".config", moved / ".config")
        shutil.copytree(ROOT / "generated", moved / "generated")
        self.load(moved / "generated", moved)
        self.assertEqual(self.tcl.getvar("cfg(CONFIG_ID)"), values(load_config())["CONFIG_ID"])


if __name__ == "__main__":
    unittest.main()
