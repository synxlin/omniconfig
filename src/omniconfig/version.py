# -*- coding: utf-8 -*-
"""Version information."""


def _get_version():
    """Get version from package metadata or pyproject.toml."""
    try:
        from importlib.metadata import version

        return version("omniconfig")
    except Exception:
        # Fallback for development - read from pyproject.toml
        try:
            import tomllib
            from pathlib import Path

            root = Path(__file__).parent.parent.parent
            with open(root / "pyproject.toml", "rb") as f:
                data = tomllib.load(f)
            return data["project"]["version"]
        except Exception:
            # Python < 3.11, use toml package which is a dependency
            try:
                from pathlib import Path

                import toml

                root = Path(__file__).parent.parent.parent
                with open(root / "pyproject.toml", "r") as f:
                    data = toml.load(f)
                return data["project"]["version"]
            except Exception:
                return "unknown"


__version__ = _get_version()
