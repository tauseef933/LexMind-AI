"""
Pure-Python xxhash-compatible API for environments where the native
``_xxhash`` extension is blocked (e.g. Windows Smart App Control).

Hashes are stable for a given input but are NOT byte-identical to real
XXH3. That is fine for local LangGraph task IDs / LangSmith helpers.
"""

from __future__ import annotations

import hashlib
from typing import Union

_Data = Union[bytes, bytearray, memoryview, str]

VERSION = "0.0.0+compat"
XXHASH_VERSION = "0.0.0+compat"

algorithms_available = {"xxh32", "xxh64", "xxh3_64", "xxh128", "xxh3_128"}
algorithms_guaranteed = algorithms_available


def _as_bytes(data: _Data) -> bytes:
    if isinstance(data, str):
        return data.encode("utf-8")
    if isinstance(data, memoryview):
        return data.tobytes()
    return bytes(data)


class _Hasher:
    def __init__(self, data: _Data = b"", seed: int = 0, *, digest_size: int, name: str):
        self._digest_size = digest_size
        self._name = name
        self._seed = int(seed) & 0xFFFFFFFFFFFFFFFF
        self._buf = bytearray()
        if data:
            self.update(data)

    def update(self, data: _Data) -> None:
        self._buf.extend(_as_bytes(data))

    def _digest_bytes(self) -> bytes:
        # blake2b is available in the stdlib and needs no native wheel.
        return hashlib.blake2b(
            bytes(self._buf),
            digest_size=self._digest_size,
            person=f"{self._name}:{self._seed}".encode("utf-8"),
        ).digest()

    def digest(self) -> bytes:
        return self._digest_bytes()

    def hexdigest(self) -> str:
        return self._digest_bytes().hex()

    def intdigest(self) -> int:
        return int.from_bytes(self._digest_bytes(), "big")

    def copy(self) -> "_Hasher":
        cloned = _Hasher(b"", seed=self._seed, digest_size=self._digest_size, name=self._name)
        cloned._buf = bytearray(self._buf)
        return cloned

    def reset(self) -> None:
        self._buf.clear()

    @property
    def digestsize(self) -> int:
        return self._digest_size

    @property
    def digest_size(self) -> int:
        return self._digest_size

    @property
    def block_size(self) -> int:
        return 64

    @property
    def name(self) -> str:
        return self._name

    @property
    def seed(self) -> int:
        return self._seed


class xxh32(_Hasher):
    def __init__(self, data: _Data = b"", seed: int = 0):
        super().__init__(data, seed, digest_size=4, name="xxh32")


class xxh64(_Hasher):
    def __init__(self, data: _Data = b"", seed: int = 0):
        super().__init__(data, seed, digest_size=8, name="xxh64")


class xxh3_64(_Hasher):
    def __init__(self, data: _Data = b"", seed: int = 0):
        super().__init__(data, seed, digest_size=8, name="xxh3_64")


class xxh3_128(_Hasher):
    def __init__(self, data: _Data = b"", seed: int = 0):
        super().__init__(data, seed, digest_size=16, name="xxh3_128")


xxh128 = xxh3_128


def xxh32_digest(data: _Data, seed: int = 0) -> bytes:
    return xxh32(data, seed).digest()


def xxh32_hexdigest(data: _Data, seed: int = 0) -> str:
    return xxh32(data, seed).hexdigest()


def xxh32_intdigest(data: _Data, seed: int = 0) -> int:
    return xxh32(data, seed).intdigest()


def xxh64_digest(data: _Data, seed: int = 0) -> bytes:
    return xxh64(data, seed).digest()


def xxh64_hexdigest(data: _Data, seed: int = 0) -> str:
    return xxh64(data, seed).hexdigest()


def xxh64_intdigest(data: _Data, seed: int = 0) -> int:
    return xxh64(data, seed).intdigest()


def xxh3_64_digest(data: _Data, seed: int = 0) -> bytes:
    return xxh3_64(data, seed).digest()


def xxh3_64_hexdigest(data: _Data, seed: int = 0) -> str:
    return xxh3_64(data, seed).hexdigest()


def xxh3_64_intdigest(data: _Data, seed: int = 0) -> int:
    return xxh3_64(data, seed).intdigest()


def xxh3_128_digest(data: _Data, seed: int = 0) -> bytes:
    return xxh3_128(data, seed).digest()


def xxh3_128_hexdigest(data: _Data, seed: int = 0) -> str:
    return xxh3_128(data, seed).hexdigest()


def xxh3_128_intdigest(data: _Data, seed: int = 0) -> int:
    return xxh3_128(data, seed).intdigest()


xxh128_digest = xxh3_128_digest
xxh128_hexdigest = xxh3_128_hexdigest
xxh128_intdigest = xxh3_128_intdigest
