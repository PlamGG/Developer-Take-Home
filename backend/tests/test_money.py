from decimal import Decimal

import pytest
from app.exceptions import BusinessRuleError
from app.services.money import (
    allocate_equal_shares,
    calculate_balances,
    format_satang_to_amount,
    parse_amount_to_satang,
    validate_exact_shares,
)


def test_strict_money_parse_and_format():
    assert parse_amount_to_satang("100.00") == 10000
    assert parse_amount_to_satang("0.01") == 1
    assert parse_amount_to_satang("10") == 1000
    assert parse_amount_to_satang("10.5") == 1050
    assert format_satang_to_amount(10000) == "100.00"
    assert format_satang_to_amount(1) == "0.01"

    # Invalid formats
    invalid_inputs = [
        "-10.00",
        "0",
        "0.00",
        "1e3",
        "NaN",
        "Infinity",
        "10.001",
        " 10.00",
        "10.00 ",
    ]
    for invalid in invalid_inputs:
        with pytest.raises(BusinessRuleError):
            parse_amount_to_satang(invalid)


def test_shared_test_vectors():
    # 1. 100.00 / 3 -> 33.34, 33.33, 33.33
    res_100 = allocate_equal_shares("100.00", ["alice", "bob", "carol"])
    assert res_100 == [("alice", "33.34"), ("bob", "33.33"), ("carol", "33.33")]

    # 2. 0.01 / 3 -> 0.01, 0.00, 0.00
    res_001 = allocate_equal_shares("0.01", ["alice", "bob", "carol"])
    assert res_001 == [("alice", "0.01"), ("bob", "0.00"), ("carol", "0.00")]

    # 3. 0.10 / 3 -> 0.04, 0.03, 0.03
    res_010 = allocate_equal_shares("0.10", ["alice", "bob", "carol"])
    assert res_010 == [("alice", "0.04"), ("bob", "0.03"), ("carol", "0.03")]

    # 4. 0.1 + 0.2 equivalent -> 0.30
    total_satang = parse_amount_to_satang("0.10") + parse_amount_to_satang("0.20")
    assert format_satang_to_amount(total_satang) == "0.30"

    # 5. Large amount -> 9999999999.99 / 2 -> 5000000000.00, 4999999999.99
    res_large = allocate_equal_shares("9999999999.99", ["alice", "bob"])
    assert res_large == [("alice", "5000000000.00"), ("bob", "4999999999.99")]


def test_equal_split_honors_request_order():
    res_bob_first = allocate_equal_shares("100.00", ["bob", "alice", "carol"])
    assert res_bob_first == [("bob", "33.34"), ("alice", "33.33"), ("carol", "33.33")]


def test_exact_validation():
    # Valid
    shares = {"alice": "50.00", "bob": "30.00", "carol": "20.00"}
    res = validate_exact_shares("100.00", shares)
    assert res == [("alice", "50.00"), ("bob", "30.00"), ("carol", "20.00")]

    # Mismatch
    bad_shares = {"alice": "50.00", "bob": "30.00"}
    with pytest.raises(BusinessRuleError) as exc_info:
        validate_exact_shares("100.00", bad_shares)
    assert exc_info.value.code == "split_mismatch"


def test_balances_calculation():
    # alice paid 100.00 for alice: 33.34, bob: 33.33, carol: 33.33
    members = ["alice", "bob", "carol"]
    expenses = [
        {
            "paid_by": "alice",
            "amount": "100.00",
            "deleted_at": None,
            "shares": [
                {"username": "alice", "amount": "33.34"},
                {"username": "bob", "amount": "33.33"},
                {"username": "carol", "amount": "33.33"},
            ],
        }
    ]
    balances = calculate_balances(members, expenses)
    assert balances == [
        {"username": "alice", "balance": "66.66"},
        {"username": "bob", "balance": "-33.33"},
        {"username": "carol", "balance": "-33.33"},
    ]
    total = sum(Decimal(b["balance"]) for b in balances)
    assert total == Decimal("0.00")
