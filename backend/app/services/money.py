import re
from collections.abc import Iterable
from typing import Any

from app.exceptions import BusinessRuleError

AMOUNT_REGEX = re.compile(r"^\d+(\.\d{1,2})?$")
MAX_SATANG = 999999999999  # 9,999,999,999.99


def parse_amount_to_satang(amount_str: str) -> int:
    """Strictly parse string amount to satang (cents)."""
    if not isinstance(amount_str, str) or not AMOUNT_REGEX.match(amount_str):
        raise BusinessRuleError(
            "invalid_amount", "Amount must be a numeric string with up to 2 decimal places"
        )

    parts = amount_str.split(".")
    baht = int(parts[0])
    satang = 0
    if len(parts) == 2:
        satang_part = parts[1]
        if len(satang_part) == 1:
            satang = int(satang_part) * 10
        elif len(satang_part) == 2:
            satang = int(satang_part)

    total_satang = baht * 100 + satang
    if total_satang <= 0:
        raise BusinessRuleError("invalid_amount", "Amount must be greater than zero")
    if total_satang > MAX_SATANG:
        raise BusinessRuleError("invalid_amount", "Amount exceeds maximum supported limit")

    return total_satang


def format_satang_to_amount(satang: int) -> str:
    """Format integer satang into fixed 2 decimal string (e.g. 100.00 or -33.33)."""
    sign = "-" if satang < 0 else ""
    abs_satang = abs(satang)
    baht = abs_satang // 100
    rem = abs_satang % 100
    return f"{sign}{baht}.{rem:02d}"


def allocate_equal_shares(amount_str: str, members: list[str]) -> list[tuple[str, str]]:
    """Allocate equal shares, distributing residual satang in request order."""
    if not members:
        raise BusinessRuleError("invalid_split", "Split members cannot be empty")

    total_satang = parse_amount_to_satang(amount_str)
    count = len(members)
    base = total_satang // count
    remainder = total_satang % count

    results: list[tuple[str, str]] = []
    for idx, member in enumerate(members):
        share_satang = base + (1 if idx < remainder else 0)
        results.append((member, format_satang_to_amount(share_satang)))

    return results


def validate_exact_shares(amount_str: str, shares: dict[str, str]) -> list[tuple[str, str]]:
    """Validate that exact shares sum to total amount and each share >= 0."""
    if not shares:
        raise BusinessRuleError("invalid_split", "Shares cannot be empty")

    total_satang = parse_amount_to_satang(amount_str)
    allocated_satang = 0
    results: list[tuple[str, str]] = []

    for member, share_str in shares.items():
        if not isinstance(share_str, str) or not AMOUNT_REGEX.match(share_str):
            raise BusinessRuleError("invalid_amount", f"Invalid share amount for {member}")
        parts = share_str.split(".")
        s_satang = int(parts[0]) * 100 + (int(parts[1].ljust(2, "0")) if len(parts) == 2 else 0)
        if s_satang < 0:
            raise BusinessRuleError("invalid_amount", f"Share cannot be negative for {member}")
        allocated_satang += s_satang
        results.append((member, format_satang_to_amount(s_satang)))

    if allocated_satang != total_satang:
        alloc_f = format_satang_to_amount(allocated_satang)
        exp_f = format_satang_to_amount(total_satang)
        raise BusinessRuleError(
            "split_mismatch",
            f"Shares sum to {alloc_f}, expected {exp_f}",
        )

    return results


def parse_satang_allow_zero(amount_str: str) -> int:
    parts = amount_str.split(".")
    satang = int(parts[0]) * 100
    if len(parts) == 2:
        satang += int(parts[1].ljust(2, "0")[:2])
    return satang


def calculate_balances(
    members: Iterable[str], expenses: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Calculate net balances for all group members from non-deleted expenses."""
    net_satang: dict[str, int] = {m: 0 for m in members}

    for exp in expenses:
        if exp.get("deleted_at") is not None:
            continue
        payer = exp["paid_by"]
        total_exp_satang = parse_amount_to_satang(exp["amount"])
        if payer in net_satang:
            net_satang[payer] += total_exp_satang

        for share in exp["shares"]:
            uname = share["username"]
            amt = share["amount"]
            s_satang = (
                int(round(float(amt) * 100))
                if isinstance(amt, float | int)
                else parse_satang_allow_zero(amt)
            )
            if uname in net_satang:
                net_satang[uname] -= s_satang

    return [{"username": m, "balance": format_satang_to_amount(net_satang[m])} for m in members]
