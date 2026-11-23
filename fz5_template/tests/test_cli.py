"""Bilingual CLI behavior and language-independent configuration contracts."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
from string import Formatter
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from configure import generate, load_config
from fz5_config.i18n import catalog


class TranslationCoverage(unittest.TestCase):
    def test_catalog_keys_and_placeholders_match(self):
        en, zh = catalog("en"), catalog("zh")
        for section in en:
            self.assertEqual(en[section].keys(), zh[section].keys(), section)
            for key, text in en[section].items():
                fields = lambda s: {name for _, name, _, _ in Formatter().parse(s) if name}
                self.assertEqual(fields(text), fields(zh[section][key]), key)

    def test_every_kconfig_prompt_and_help_has_a_translation(self):
        k = load_config()
        for node in [k.top_node, *k.node_iter()]:
            if node.prompt:
                self.assertIn(node.prompt[0], catalog("zh")["prompts"])
            if getattr(node, "help", None):
                self.assertIn(node.item.name, catalog("zh")["help"])


class BilingualCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="FZ5 bilingual CLI ")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.cfg = self.work / "用户 config.config"
        self.out = self.work / "generated files"
        with redirect_stdout(io.StringIO()):
            generate(load_config(ROOT / "configs/fz5d_defconfig"), self.out, config_path=self.cfg)

    def run_cli(self, *args, input=None, env=None):
        environment = os.environ.copy()
        environment.update(env or {})
        return subprocess.run([sys.executable, "-m", "fz5_config", "--config", str(self.cfg), "--out", str(self.out), *args], cwd=self.work, input=input, capture_output=True, text=True, encoding="utf-8", env=environment)

    def files(self):
        return {p.name: p.read_bytes() for p in [self.cfg, *self.out.glob("*")] if p.is_file()}

    def test_language_flags_on_either_side_of_subcommand(self):
        zh = self.run_cli("--lang", "zh", "describe", "PL_RESERVED_MB")
        en = self.run_cli("describe", "PL_RESERVED_MB", "--lang", "en")
        self.assertEqual(zh.returncode, 0, zh.stderr)
        self.assertEqual(en.returncode, 0, en.stderr)
        self.assertIn("范围: 0..6144", zh.stdout)
        self.assertIn("Range: 0..6144", en.stdout)

    def test_help_supports_both_languages(self):
        r = self.run_cli("--lang", "both", "--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("子命令", r.stdout)
        self.assertIn("commands", r.stdout)
        self.assertIn("启用布尔选项", r.stdout)
        self.assertIn("enable boolean options", r.stdout)

    def test_environment_language_and_explicit_override(self):
        env = {"FZ5_LANG": "zh"}
        self.assertIn("子命令", self.run_cli("--help", env=env).stdout)
        self.assertIn("commands", self.run_cli("--lang", "en", "--help", env=env).stdout)

    def test_json_and_saved_artifacts_are_identical_across_languages(self):
        previous_json = previous_files = None
        for lang in ("zh", "en", "both"):
            r = self.run_cli("--lang", lang, "set", "PL_RESERVED_MB=2048", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            data, files = json.loads(r.stdout), self.files()
            if previous_json is not None:
                self.assertEqual(data, previous_json)
                self.assertEqual(files, previous_files)
            previous_json, previous_files = data, files

    def test_get_provides_a_raw_value_for_scripts(self):
        r = self.run_cli("--lang", "both", "get", "CONFIG_PL_RESERVED_MB")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1024")

    def test_get_accepts_the_canonical_config_id(self):
        r = self.run_cli("--lang", "en", "get", "CONFIG_ID")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.strip(), r"^[0-9a-f]{64}$")

    def test_search_matches_chinese_help_in_english_mode(self):
        r = self.run_cli("--lang", "en", "search", "隔离", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PL_RESERVED_MB", [x["name"] for x in json.loads(r.stdout)])

    def test_hidden_option_describes_its_dependency(self):
        r = self.run_cli("--lang", "zh", "describe", "PS_USB3", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertFalse(data["available"])
        self.assertIn("PS_USB0", data["dependency"])

    def test_dependency_error_is_localized_and_does_not_write(self):
        old = self.files()
        r = self.run_cli("--lang", "zh", "enable", "PS_USB3")
        self.assertEqual(r.returncode, 1)
        self.assertIn("依赖", r.stderr)
        self.assertEqual(self.files(), old)

    def test_enable_disable_and_quiet_mode(self):
        r = self.run_cli("--lang", "en", "disable", "PS_GEM3", "--quiet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        r = self.run_cli("--lang", "zh", "enable", "PS_GEM3", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)["PS_GEM3"])

    def test_usage_error_has_exit_code_two_and_translated_message(self):
        r = self.run_cli("--lang", "zh", "set")
        self.assertEqual(r.returncode, 2)
        self.assertIn("缺少必填参数", r.stderr)

    def test_interactive_menu_requires_a_terminal_without_writing(self):
        old = self.files()
        r = self.run_cli("--lang", "zh", "menu", input="l\nq\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("交互终端", r.stderr)
        self.assertEqual(self.files(), old)

    def test_installed_entry_point_runs_outside_the_project_directory(self):
        executable = Path(sys.executable).parent / ("fz5-config.exe" if os.name == "nt" else "fz5-config")
        if not executable.exists():
            self.skipTest("Use uv sync to install the console entry point")
        r = subprocess.run([str(executable), "--template", str(ROOT), "--lang", "en", "get", "PL_RESERVED_MB"], cwd=self.work, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1024")


if __name__ == "__main__":
    unittest.main()
