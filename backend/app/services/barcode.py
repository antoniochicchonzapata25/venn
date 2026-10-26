"""Barcode normalisation and validation (GTIN-8, UPC-A, EAN-13, GTIN-14)."""

from __future__ import annotations

VALID_LENGTHS = (8, 12, 13, 14)


class BarcodeError(ValueError):
    pass


def check_digit_ok(code: str) -> bool:
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def normalize(raw: str) -> str:
    """Strip spaces/dashes, validate, and return the zero-padded 14-digit GTIN."""
    code = "".join(ch for ch in (raw or "") if not ch.isspace() and ch != "-")
    if not code.isdigit():
        raise BarcodeError("A barcode contains digits only.")
    if len(code) not in VALID_LENGTHS:
        raise BarcodeError("Barcodes have 8, 12, 13 or 14 digits.")
    if not check_digit_ok(code):
        raise BarcodeError("The last digit (check digit) doesn't match. Please re-check the number.")
    return code.zfill(14)
