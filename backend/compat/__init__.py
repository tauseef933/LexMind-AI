"""Compatibility shims for restricted Windows environments."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("lexmind.compat")


def ensure_xxhash() -> None:
    """
    Ensure ``import xxhash`` works even when Smart App Control blocks the
    native ``_xxhash*.pyd`` extension.
    """
    try:
        import xxhash as _xx  # noqa: F401

        # Touch a symbol that requires the native module.
        _ = _xx.xxh3_128_hexdigest(b"lexmind")
        return
    except Exception as exc:  # ImportError / OSError from App Control
        logger.warning(
            "Native xxhash unavailable (%s); using pure-Python compatibility shim.",
            exc,
        )

    sys.modules.pop("xxhash", None)
    sys.modules.pop("xxhash._xxhash", None)
    sys.modules.pop("xxhash.version", None)

    from compat import xxhash_shim

    sys.modules["xxhash"] = xxhash_shim
