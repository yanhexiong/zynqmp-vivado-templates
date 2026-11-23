"""UI translations only: language never enters the hardware configuration."""
from __future__ import annotations

from functools import lru_cache
import json
import locale
import os
from pathlib import Path


@lru_cache(maxsize=2)
def catalog(language: str) -> dict:
    return json.loads((Path(__file__).parent / "locales" / f"{language}.json").read_text(encoding="utf-8"))


def resolve_language(requested: str | None = None) -> str:
    selected = requested or os.environ.get("AXU4EV_LANG", "auto")
    if selected not in ("auto", "zh", "en", "both"):
        raise ValueError(f"Unsupported language: {selected}; choose zh, en, both or auto")
    if selected != "auto":
        return selected
    detected = next((os.environ[name] for name in ("LC_ALL", "LC_MESSAGES", "LANG") if os.environ.get(name)), None)
    if detected is None:
        detected = locale.getlocale()[0] or "en"
    return "zh" if detected.lower().startswith(("zh", "chinese")) else "en"


class Translator:
    def __init__(self, language: str = "en"):
        self.language = language

    def render(self, section: str, key: str, **params) -> str:
        en = catalog("en")[section][key].format(**params)
        if self.language == "en":
            return en
        zh = catalog("zh")[section][key].format(**params)
        if self.language == "zh":
            return zh
        return zh if zh == en else f"{zh} / {en}"

    def t(self, key: str, **params) -> str:
        return self.render("messages", key, **params)

    def prompt(self, original: str) -> str:
        if original not in catalog("en")["prompts"]:
            return original
        return self.render("prompts", original)

    def help(self, name: str, original: str) -> str:
        if name not in catalog("en")["help"]:
            return original
        return self.render("help", name)

    def error(self, error: Exception) -> str:
        if isinstance(error, ConfigError):
            return self.t(error.key, **error.params)
        return str(error)

    def cycle(self) -> None:
        self.language = {"en": "zh", "zh": "both", "both": "en"}[self.language]


class ConfigError(ValueError):
    """Structured errors keep the library's English compatibility and localize UI."""
    def __init__(self, key: str, **params):
        self.key, self.params = key, params
        super().__init__(Translator("en").t(key, **params))
