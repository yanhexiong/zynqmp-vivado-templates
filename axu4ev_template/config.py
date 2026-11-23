"""Compatibility entry: no arguments opens the menu; prefer uv run axu4ev-config."""
from axu4ev_config.cli import entrypoint

if __name__ == "__main__":
    entrypoint(default_menu=True)
