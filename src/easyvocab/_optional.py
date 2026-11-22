"""Lazy imports for optional extras, so `import easyvocab` works without them."""

import importlib
from types import ModuleType

from easyvocab.errors import MissingExtraError


def require(module: str, extra: str) -> ModuleType:
    """Import an optional dependency or raise `MissingExtraError` with the install command."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise MissingExtraError(module.split(".")[0], extra) from exc
