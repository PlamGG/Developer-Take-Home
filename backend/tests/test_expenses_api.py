from app.main import create_app
from fastapi.testclient import TestClient

client = TestClient(create_app())


def test_missing_x_user():
    res = client.get("/groups")
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "unauthorized"


def test_unknown_x_user():
    res = client.get("/groups", headers={"X-User": "nonexistent"})
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "unauthorized"


def test_list_groups_for_alice():
    res = client.get("/groups", headers={"X-User": "alice"})
    assert res.status_code == 200
    groups = res.json()
    assert len(groups) == 1
    assert groups[0]["id"] == 1
    assert groups[0]["name"] == "Chiang Mai trip"
    assert "alice" in groups[0]["members"]


def test_get_group_detail():
    # Alice gets group 1
    res = client.get("/groups/1", headers={"X-User": "alice"})
    assert res.status_code == 200
    assert res.json()["name"] == "Chiang Mai trip"

    # Alice gets nonexistent group 999
    res_404 = client.get("/groups/999", headers={"X-User": "alice"})
    assert res_404.status_code == 404

    # Alice gets group 2 (she is not a member) -> 403 not_a_member
    res_403 = client.get("/groups/2", headers={"X-User": "alice"})
    assert res_403.status_code == 403
    assert res_403.json()["detail"]["code"] == "not_a_member"


def test_idempotent_expense_creation():
    payload = {
        "description": "Lunch at market",
        "paid_by": "alice",
        "amount": "100.00",
        "split": {
            "type": "equal",
            "members": ["alice", "bob", "carol"],
        },
    }
    import uuid

    headers = {"X-User": "alice", "Idempotency-Key": f"test-key-{uuid.uuid4()}"}

    # 1. First create -> 201
    res1 = client.post("/groups/1/expenses", json=payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["amount"] == "100.00"
    assert len(data1["shares"]) == 3

    # 2. Replay with same key -> 200 and same expense ID
    res2 = client.post("/groups/1/expenses", json=payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["id"] == data1["id"]

    # 3. Missing idempotency key -> 422
    res_no_key = client.post("/groups/1/expenses", json=payload, headers={"X-User": "alice"})
    assert res_no_key.status_code == 422
