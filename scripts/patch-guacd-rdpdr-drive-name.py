"""Patch the Guacamole 1.6.0 RDPDR device-name length bug.

The upstream 1.6.0 implementation uses Unicode character count when writing
UTF-8 bytes into the RDPDR filesystem device announcement. The patch redirects
that one call to strlen, which makes the announced byte length match the data.
The exact library hash and call bytes are checked before writing.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


EXPECTED_SHA256 = "00e12f90104aaa8cffc0b0b8ab461ff1f774e7b2c45c47b978e3b7e2d088e729"
CALL_OFFSET = 0x1A770
ORIGINAL_CALL = bytes.fromhex("e8 8b 46 ff ff")
PATCHED_CALL = bytes.fromhex("e8 0b 42 ff ff")


def patch_bytes(data: bytes) -> bytes:
    end = CALL_OFFSET + len(ORIGINAL_CALL)
    if len(data) < end:
        raise ValueError("RDP client library is shorter than the pinned patch site")

    current = data[CALL_OFFSET:end]
    if current == PATCHED_CALL:
        raise ValueError("RDPDR byte-length patch is already applied")
    if current != ORIGINAL_CALL:
        raise ValueError(
            f"unexpected bytes at 0x{CALL_OFFSET:x}: {current.hex()}"
        )

    patched = bytearray(data)
    patched[CALL_OFFSET:end] = PATCHED_CALL
    return bytes(patched)


def patch_file(input_path: Path, output_path: Path, expected_sha256: str) -> str:
    original = input_path.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError(
            f"unexpected source SHA-256: {digest}; expected {expected_sha256}"
        )

    output = patch_bytes(original)
    output_path.write_bytes(output)
    return hashlib.sha256(output).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    args = parser.parse_args()

    patched_sha256 = patch_file(args.input, args.output, args.expected_sha256)
    print(patched_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
