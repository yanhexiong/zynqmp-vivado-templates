"""Cross-platform toolchain discovery, multi-version selection, and Tcl safety tests."""
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import zynqmp_host as host  # noqa: E402

try:
    import tkinter
except ImportError:
    tkinter = None
else:
    try:
        tkinter.Tcl()
    except tkinter.TclError:
        tkinter = None


def _make_fake_install(root: Path, product: str, *, is_windows: bool, with_xsct: bool = True, with_bootgen: bool = True) -> None:
    suffix = ".bat" if is_windows else ""
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    if product == "Vivado":
        (bin_dir / f"vivado{suffix}").write_text("", encoding="utf-8")
    else:
        (bin_dir / f"vitis{suffix}").write_text("", encoding="utf-8")
        if with_xsct:
            (bin_dir / f"xsct{suffix}").write_text("", encoding="utf-8")
    if with_bootgen:
        (bin_dir / f"bootgen{suffix}").write_text("", encoding="utf-8")


class ToolchainDiscoveryTests(unittest.TestCase):
    def test_discovers_both_standard_and_amd_layouts_on_linux_and_windows(self):
        for is_win in (False, True):
            with self.subTest(is_windows=is_win), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp) / "Xilinx"
                v2023 = base / "Vivado" / "2023.1"
                v2024 = base / "Vivado" / "2024.1"
                v2025 = base / "2025.1" / "Vivado"
                t2023 = base / "Vitis" / "2023.1"
                t2025 = base / "2025.1" / "Vitis"
                _make_fake_install(v2023, "Vivado", is_windows=is_win)
                _make_fake_install(v2024, "Vivado", is_windows=is_win)
                _make_fake_install(v2025, "Vivado", is_windows=is_win)
                _make_fake_install(t2023, "Vitis", is_windows=is_win, with_xsct=True)
                _make_fake_install(t2025, "Vitis", is_windows=is_win, with_xsct=False)

                installs = host.discover_toolchains(env={}, search_bases=[base], is_windows=is_win)
                vivados = [i for i in installs if i.product == "Vivado"]
                vitises = [i for i in installs if i.product == "Vitis"]

                self.assertEqual([i.version for i in vivados], ["2023.1", "2025.1", "2024.1"])
                self.assertTrue(vivados[0].is_validated)
                self.assertFalse(vivados[1].is_validated)
                self.assertEqual([(i.version, i.has_xsct) for i in vitises], [("2023.1", True), ("2025.1", False)])

                chosen_default = host.select_toolchain("Vivado", env={}, search_bases=[base], is_windows=is_win)
                self.assertEqual(chosen_default.version, "2023.1")

                chosen_2024 = host.select_toolchain("Vivado", tool_version="2024.1", env={}, search_bases=[base], is_windows=is_win)
                self.assertEqual(chosen_2024.root, v2024)

                listing = host.format_toolchains(installs)
                self.assertIn("2023.1", listing)
                self.assertIn("2025.1", listing)
                self.assertIn("validated", listing)

    def test_explicit_dir_and_env_override_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "AMD"
            v2023 = base / "Vivado" / "2023.1"
            v2024 = base / "Vivado" / "2024.2"
            _make_fake_install(v2023, "Vivado", is_windows=False)
            _make_fake_install(v2024, "Vivado", is_windows=False)

            chosen_env = host.select_toolchain("Vivado", env={"XILINX_VIVADO": str(v2024)}, search_bases=[base], is_windows=False)
            self.assertEqual(chosen_env.version, "2024.2")

            chosen_explicit = host.select_toolchain(
                "Vivado",
                tool_dir=v2023,
                env={"XILINX_VIVADO": str(v2024)},
                search_bases=[base],
                is_windows=False,
            )
            self.assertEqual(chosen_explicit.version, "2023.1")

            with self.assertRaises(FileNotFoundError):
                host.select_toolchain("Vivado", tool_version="2099.1", env={}, search_bases=[base], is_windows=False)


@unittest.skipIf(tkinter is None, "Optional Tcl interpreter not installed")
class TclVersionAndPythonTests(unittest.TestCase):
    def test_project_lib_warns_by_default_and_errors_when_strict(self):
        for template in ("fz5_template", "axu4ev_template"):
            with self.subTest(template=template):
                tcl = tkinter.Tcl()
                tcl.eval("proc version {arg} { return 2024.1 }")
                tcl.eval(f"source {{{(REPO_ROOT / template / 'tcl/project_lib.tcl').as_posix()}}}")
                ns = "fz5" if template == "fz5_template" else "axu4ev"
                # With ZYNQMP_STRICT_VERSION=1, mismatch fails immediately at version check.
                tcl.eval("set ::env(ZYNQMP_STRICT_VERSION) 1")
                with self.assertRaisesRegex(tkinter.TclError, "ZYNQMP_STRICT_VERSION=1"):
                    tcl.eval(f"::{ns}::initialize")
                # Without strict mode, version check passes and proceeds to configuration load.
                tcl.eval("unset -nocomplain ::env(ZYNQMP_STRICT_VERSION)")
                out = tcl.eval(
                    f"catch {{::{ns}::initialize {{nonexistent-dir}}}} msg; set msg"
                )
                self.assertIn("Missing", out)


if __name__ == "__main__":
    unittest.main()
