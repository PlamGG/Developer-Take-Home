import concurrent.futures
import uuid

from app.database import SessionLocal
from app.main import create_app
from app.schemas import CreateExpenseRequest, SplitEqual
from app.services.expense import create_expense, get_current_user
from fastapi.testclient import TestClient

app = create_app()
client = TestClient(app)


def test_access_control_across_routes():
    # Alice is not a member of Group 2 (Office lunch)
    # Check 1: Missing X-User -> 401
    r_no_auth = client.get("/groups/2")
    assert r_no_auth.status_code == 401
    assert r_no_auth.json()["detail"]["code"] == "unauthorized"

    # Check 2: Alice attempts GET /groups/2 -> 403 not_a_member
    r_get = client.get("/groups/2", headers={"X-User": "alice"})
    assert r_get.status_code == 403
    assert r_get.json()["detail"]["code"] == "not_a_member"
    assert r_get.json()["detail"]["message"] == "Not a member of this group"

    # Check 3: Alice attempts POST /groups/2/expenses -> 403 not_a_member
    r_post = client.post(
        "/groups/2/expenses",
        headers={"X-User": "alice", "Idempotency-Key": f"key-{uuid.uuid4()}"},
        json={
            "description": "Unauthorized lunch",
            "paid_by": "bob",
            "amount": "50.00",
            "split": {"type": "equal", "members": ["bob", "dan"]},
        },
    )
    assert r_post.status_code == 403
    assert r_post.json()["detail"]["code"] == "not_a_member"


def test_concurrent_idempotent_expense_creation():
    shared_key = f"concurrent-{uuid.uuid4()}"
    group_id = 1

    def run_create():
        db = SessionLocal()
        try:
            user = get_current_user(db, "alice")
            req = CreateExpenseRequest(
                description="Team Dinner",
                paid_by="alice",
                amount="300.00",
                split=SplitEqual(type="equal", members=["alice", "bob", "carol"]),
            )
            resp, status_code = create_expense(
                db=db,
                group_id=group_id,
                requester=user,
                idempotency_key=shared_key,
                payload=req,
            )
            return resp, status_code
        finally:
            db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(run_create)
        f2 = executor.submit(run_create)
        res1, status1 = f1.result()
        res2, status2 = f2.result()

    # Both requests must return the exact same expense ID and total amount
    assert res1.id == res2.id
    assert res1.amount == "300.00"
    assert res2.amount == "300.00"
    # One is 201 (created), the other is 200 (idempotent replay)
    statuses = {status1, status2}
    assert 201 in statuses
    assert 200 in statuses
