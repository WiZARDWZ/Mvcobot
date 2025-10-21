"""Private Telegram bot integration package."""

# Expose key submodules for convenience when imported as a package.
from .config.settings import settings  # noqa: F401

__all__ = ["settings"]
