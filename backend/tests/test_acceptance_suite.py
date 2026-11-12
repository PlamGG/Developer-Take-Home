import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.database import SessionLocal
from app.main import create_app
from app.models import Expense, ExpenseShare
from fastapi.testclient import TestClient

client = TestClient(create_app())


def test_complete_flow_and_acceptance_checks():
    # 1. Equal 100.00 among three members gives 33.34, 33.33, 33.33; balances total 0.00.
    key1 = f"flow-key-{uuid.uuid4()}"
    p1 = {
        "description": "Dinner",
        "paid_by": "alice",
        "amount": "100.00",
        "split": {"type": "equal", "members": ["alice", "bob", "carol"]},
    }
    r1 = client.post(
        "/groups/1/expenses",
        json=p1,
        headers={"X-User": "alice", "Idempotency-Key": key1},
    )
    assert r1.status_code == 201
    exp1 = r1.json()
    assert [s["amount"] for s in exp1["shares"]] == ["33.34", "33.33", "33.33"]

    # Check Balances
    b_res = client.get("/groups/1/balances", headers={"X-User": "alice"})
    assert b_res.status_code == 200
    b_data = b_res.json()["balances"]
    assert sum(Decimal(b["balance"]) for b in b_data) == Decimal("0.00")

    # 2. Equal split honors request order (bob, alice, carol gives bob the extra satang)
    key2 = f"flow-key-{uuid.uuid4()}"
    p2 = {
        "description": "Drinks",
        "paid_by": "bob",
        "amount": "100.00",
        "split": {"type": "equal", "members": ["bob", "alice", "carol"]},
    }
    r2 = client.post(
        "/groups/1/expenses",
        json=p2,
        headers={"X-User": "bob", "Idempotency-Key": key2},
    )
    assert r2.status_code == 201
    exp2 = r2.json()
    assert exp2["shares"][0]["username"] == "bob"
    assert exp2["shares"][0]["amount"] == "33.34"

    # 3. Exact split not summing to amount is rejected
    key3 = f"flow-key-{uuid.uuid4()}"
    p3 = {
        "description": "Snacks",
        "paid_by": "alice",
        "amount": "100.00",
        "split": {"type": "exact", "shares": {"alice": "50.00", "bob": "40.00"}},
    }
    r3 = client.post(
        "/groups/1/expenses",
        json=p3,
        headers={"X-User": "alice", "Idempotency-Key": key3},
    )
    assert r3.status_code == 422
    assert r3.json()["detail"]["code"] == "split_mismatch"

    # 4. Amount validation: zero, negative, 3 decimals, malformed, non-string numeric
    bad_amounts = ["0", "0.00", "-10.00", "10.001", "1e3", "NaN"]
    for bad in bad_amounts:
        p_bad = {
            "description": "Bad amount",
            "paid_by": "alice",
            "amount": bad,
            "split": {"type": "equal", "members": ["alice", "bob"]},
        }
        r_bad = client.post(
            "/groups/1/expenses",
            json=p_bad,
            headers={"X-User": "alice", "Idempotency-Key": f"k-{uuid.uuid4()}"},
        )
        assert r_bad.status_code == 422

    # Numeric amount without quotes (raw float/int in JSON)
    r_numeric = client.post(
        "/groups/1/expenses",
        json={
            "description": "Numeric",
            "paid_by": "alice",
            "amount": 10.5,
            "split": {"type": "equal", "members": ["alice", "bob"]},
        },
        headers={"X-User": "alice", "Idempotency-Key": f"k-{uuid.uuid4()}"},
    )
    assert r_numeric.status_code == 422

    # 5. Description validation: empty, whitespace-only, over 200 chars
    for bad_desc in ["", "   ", "A" * 201]:
        r_desc = client.post(
            "/groups/1/expenses",
            json={
                "description": bad_desc,
                "paid_by": "alice",
                "amount": "10.00",
                "split": {"type": "equal", "members": ["alice", "bob"]},
            },
            headers={"X-User": "alice", "Idempotency-Key": f"k-{uuid.uuid4()}"},
        )
        assert r_desc.status_code == 422
        assert r_desc.json()["detail"]["code"] == "invalid_description"

    # 6. Payer or split member outside the group
    r_payer_outside = client.post(
        "/groups/1/expenses",
        json={
            "description": "Dan pays",
            "paid_by": "dan",  # Dan is in group 2 only
            "amount": "50.00",
            "split": {"type": "equal", "members": ["alice", "bob"]},
        },
        headers={"X-User": "alice", "Idempotency-Key": f"k-{uuid.uuid4()}"},
    )
    assert r_payer_outside.status_code == 422
    assert r_payer_outside.json()["detail"]["code"] == "invalid_payer"

    r_member_outside = client.post(
        "/groups/1/expenses",
        json={
            "description": "Dan splits",
            "paid_by": "alice",
            "amount": "50.00",
            "split": {"type": "equal", "members": ["alice", "dan"]},
        },
        headers={"X-User": "alice", "Idempotency-Key": f"k-{uuid.uuid4()}"},
    )
    assert r_member_outside.status_code == 422
    assert r_member_outside.json()["detail"]["code"] == "invalid_split"

    # 7. Tiny amounts (0.02 among 3 -> 0.01, 0.01, 0.00)
    key_tiny = f"tiny-{uuid.uuid4()}"
    r_tiny = client.post(
        "/groups/1/expenses",
        json={
            "description": "Tiny",
            "paid_by": "alice",
            "amount": "0.02",
            "split": {"type": "equal", "members": ["alice", "bob", "carol"]},
        },
        headers={"X-User": "alice", "Idempotency-Key": key_tiny},
    )
    assert r_tiny.status_code == 201
    assert [s["amount"] for s in r_tiny.json()["shares"]] == ["0.01", "0.01", "0.00"]

    # 8. Replay with malformed body returns 422; replay with different body returns original 200
    r_rep_mal = client.post(
        "/groups/1/expenses",
        json={"invalid": "body"},
        headers={"X-User": "alice", "Idempotency-Key": key_tiny},
    )
    assert r_rep_mal.status_code == 422

    r_rep_diff = client.post(
        "/groups/1/expenses",
        json={
            "description": "Completely different text",
            "paid_by": "bob",
            "amount": "99.00",
            "split": {"type": "equal", "members": ["bob", "carol"]},
        },
        headers={"X-User": "alice", "Idempotency-Key": key_tiny},
    )
    assert r_rep_diff.status_code == 200
    assert r_rep_diff.json()["id"] == r_tiny.json()["id"]
    assert r_rep_diff.json()["description"] == "Tiny"

    # 9. Soft-delete authorization and behavior
    # Bob tries to delete Alice's expense (exp1) -> 403
    r_del_bob = client.delete(f"/groups/1/expenses/{exp1['id']}", headers={"X-User": "bob"})
    assert r_del_bob.status_code == 403
    assert r_del_bob.json()["detail"]["code"] == "forbidden_delete"

    # Alice deletes her own expense -> 204
    r_del_alice = client.delete(f"/groups/1/expenses/{exp1['id']}", headers={"X-User": "alice"})
    assert r_del_alice.status_code == 204

    # Alice tries to delete already deleted expense -> 404
    r_del_again = client.delete(f"/groups/1/expenses/{exp1['id']}", headers={"X-User": "alice"})
    assert r_del_again.status_code == 404

    # Nonexistent expense in group -> 404
    r_del_none = client.delete("/groups/1/expenses/999999", headers={"X-User": "alice"})
    assert r_del_none.status_code == 404

    # Soft-deleted expense absent from listing and balances
    r_list = client.get("/groups/1/expenses", headers={"X-User": "alice"})
    assert r_list.status_code == 200
    exp_ids = [e["id"] for e in r_list.json()]
    assert exp1["id"] not in exp_ids

    # Replay of key whose expense was soft-deleted returns original
    r_rep_del = client.post(
        "/groups/1/expenses",
        json=p1,
        headers={"X-User": "alice", "Idempotency-Key": key1},
    )
    assert r_rep_del.status_code == 200
    assert r_rep_del.json()["id"] == exp1["id"]
    assert r_rep_del.json()["deleted_at"] is not None


def test_listing_tie_breaker_created_at():
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        k_a = f"tie-a-{uuid.uuid4()}"
        k_b = f"tie-b-{uuid.uuid4()}"
        exp_a = Expense(
            group_id=1,
            payer_id=1,
            description="Tie A",
            amount=Decimal("10.00"),
            idempotency_key=k_a,
            created_at=now,
        )
        exp_b = Expense(
            group_id=1,
            payer_id=1,
            description="Tie B",
            amount=Decimal("10.00"),
            idempotency_key=k_b,
            created_at=now,
        )
        db.add(exp_a)
        db.add(exp_b)
        db.flush()
        db.add(ExpenseShare(expense_id=exp_a.id, user_id=1, amount=Decimal("10.00")))
        db.add(ExpenseShare(expense_id=exp_b.id, user_id=1, amount=Decimal("10.00")))
        db.commit()

        res = client.get("/groups/1/expenses", headers={"X-User": "alice"})
        assert res.status_code == 200
        items = res.json()
        ids = [item["id"] for item in items if item["id"] in (exp_a.id, exp_b.id)]
        assert ids == [max(exp_a.id, exp_b.id), min(exp_a.id, exp_b.id)]
    finally:
        db.close()
