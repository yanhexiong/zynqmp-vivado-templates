"""Compatibility entry: no arguments opens the menu; prefer uv run fz5-config."""
from fz5_config.cli import entrypoint

if __name__ == "__main__":
    entrypoint(default_menu=True)
