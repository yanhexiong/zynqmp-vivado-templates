"""Contract tests: geometry holes, partition bounds and disabled dependencies."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from configure import ROOT, load_config, values, generate


class MemoryContract(unittest.TestCase):
    def test_missing_profile_is_an_error(self):
        with self.assertRaises(ValueError):
            load_config(ROOT / "configs/does-not-exist")

    def test_profiles(self):
        for profile, gib in [("fz5d", 8), ("fz5c", 4), ("minimal", 8), ("full", 8)]:
            with self.subTest(profile=profile):
                v = values(load_config(ROOT / "configs" / f"{profile}_defconfig"))
                self.assertEqual(v["DDR_TOTAL_BYTES"], gib << 30)
                self.assertEqual(v["DDR_LOW_SIZE"] + v["DDR_HIGH_SIZE"], gib << 30)
                self.assertEqual(v["DDR_HIGH_BASE"], 0x800000000)
                self.assertEqual(v["PS_AVAILABLE_BYTES"] + v["PL_POOL_SIZE"], gib << 30)
                if v["PL_POOL_SIZE"]:
                    self.assertEqual(v["PL_POOL_BASE"] + v["PL_POOL_SIZE"], v["DDR_HIGH_BASE"] + v["DDR_HIGH_SIZE"])
                else:
                    self.assertFalse(v["PL_DMA"])
                self.assertEqual(v["RUN_LED_MIO"], 43)
                self.assertEqual(v["FAN_CTRL_MIO"], 42)

    def test_usb_dependency(self):
        k = load_config(ROOT / "configs/minimal_defconfig")
        k.syms["PS_USB3"].set_value(2)
        self.assertFalse(values(k)["PS_USB3"])

    def test_reject_out_of_range_instead_of_defaulting(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".config"
            f.write_text("CONFIG_BOARD_FZ5C=y\nCONFIG_PL_RESERVED_MB=6144\n")
            with self.assertRaises(ValueError):
                load_config(f)

    def test_reject_unaligned_pool(self):
        k = load_config(ROOT / "configs/fz5d_defconfig")
        k.syms["PL_RESERVED_MB"].set_value("513")
        with self.assertRaises(ValueError):
            values(k)

    def test_menu_range_is_not_silently_replaced(self):
        k = load_config(ROOT / "configs/fz5d_defconfig")
        k.syms["PL_RESERVED_MB"].set_value("9000")
        with self.assertRaises(ValueError):
            values(k)

    def test_dtsi_high_address_cells(self):
        k = load_config(ROOT / "configs/fz5d_defconfig")
        with tempfile.TemporaryDirectory() as d:
            v = generate(k, Path(d), save=False)
            self.assertIn("0x9 0x40000000 0x0 0x40000000", (Path(d) / "fz5-memory.dtsi").read_text())
            self.assertEqual(v["PL_POOL_BASE"], 0x940000000)


if __name__ == "__main__":
    unittest.main()
