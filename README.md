# SplitBill

Shared-expense application built with FastAPI, Next.js, and PostgreSQL. This repository is being developed for the Chowpa Developer Take-Home Test.

## Status and time log

| Milestone | Started | Finished | Notes |
| --- | --- | --- | --- |
| 0 - API contract | 2026-11-13 | 2026-11-13 | Contract and assumptions locked before implementation. |
| 1 - Project scaffold | 2026-11-13 | 2026-11-13 | Local backend and frontend toolchains configured. |

Approximate time is updated as milestones are completed.

## API contract

### Authentication and group access

Requests identify their user with the `X-User` header. Full authentication is intentionally out of scope.

Every group-scoped endpoint applies checks in this exact order:

1. A missing or unknown `X-User` returns `401`.
2. A nonexistent group returns `404`.
3. A known user who is not a member of the group returns `403` with `not_a_member`.
4. Invalid request bodies return `422`.
5. Business-rule violations return `422` with a specific code.

This application deliberately uses `403` rather than hiding an existing group behind `404`: groups are not considered sensitive in this scoped exercise and a clear permission error matches the product requirement. The trade-off is that it reveals that a group ID exists.

All failures use the same shape:

```json
{
  "detail": {
    "code": "not_a_member",
    "message": "Not a member of this group"
  }
}
```

### Money

All monetary request and response values are JSON strings with exactly two decimal places when returned, for example `"1000.00"`. The backend accepts only strings matching `^\\d+(\\.\\d{1,2})?$`, normalizes accepted values to two decimals, and rejects JSON numeric values, exponent notation, whitespace, signs, `NaN`, `Infinity`, amounts over `9999999999.99`, zero, negative values, and more than two decimal places.

Python calculations use `Decimal`, PostgreSQL stores money in `NUMERIC(12,2)`, and no backend monetary path may use `float`. The frontend will use integer satang for arithmetic and formatting only at the display boundary.

### Endpoints

| Method | Path | Success | Description |
| --- | --- | --- | --- |
| GET | `/groups` | 200 | List groups of the requesting user. |
| GET | `/groups/{group_id}` | 200 | Return a group and its members. |
| POST | `/groups/{group_id}/expenses` | 201/200 | Create an expense or replay an idempotent request. |
| GET | `/groups/{group_id}/expenses` | 200 | List non-deleted expenses, newest first. |
| DELETE | `/groups/{group_id}/expenses/{expense_id}` | 204 | Soft-delete an expense when requested by its payer. |
| GET | `/groups/{group_id}/balances` | 200 | Return all group-member balances. |

`GET /groups/{group_id}` returns:

```json
{"id": 1, "name": "Chiang Mai trip", "members": ["alice", "bob", "carol"]}
```

Expense creation requires `X-User` and a non-empty `Idempotency-Key` header of at most 255 characters. Its request body is:

```json
{
  "description": "Dinner at the night market",
  "paid_by": "alice",
  "amount": "1000.00",
  "split": {
    "type": "equal",
    "members": ["alice", "bob", "carol"]
  }
}
```

For an exact split, `split` is:

```json
{
  "type": "exact",
  "shares": {"alice": "500.00", "bob": "300.00", "carol": "200.00"}
}
```

An expense response is:

```json
{
  "id": 1,
  "group_id": 1,
  "description": "Dinner at the night market",
  "paid_by": "alice",
  "amount": "1000.00",
  "created_at": "2026-11-13T00:00:00Z",
  "deleted_at": null,
  "shares": [
    {"username": "alice", "amount": "333.34"},
    {"username": "bob", "amount": "333.33"},
    {"username": "carol", "amount": "333.33"}
  ]
}
```

Balances return every group member in ascending user-ID order:

```json
{
  "group_id": 1,
  "balances": [
    {"username": "alice", "balance": "666.66"},
    {"username": "bob", "balance": "-333.33"},
    {"username": "carol", "balance": "-333.33"}
  ]
}
```

### Expense rules

- Descriptions are trimmed, must be non-empty, and must not exceed 200 characters. Violations return `422` with `invalid_description`.
- The requester must be a group member. `paid_by` may be any group member; the requester may record an expense paid by another member.
- A payer and every member in a split must be group members. Split members must be unique and equal splits must contain at least one member.
- Equal-split residual satang is assigned one at a time in the order in `split.members`. Thus `100.00` split among `alice`, `bob`, `carol` is `33.34`, `33.33`, `33.33`.
- The frontend will always submit selected members in the member-list order returned by the group endpoint, rather than click order, so its preview is deterministic and agrees with the backend.
- Exact shares must be non-negative and add to the expense amount exactly. A mismatch returns a descriptive error that includes expected and actual totals.
- Balance equals money paid minus shares owed. Positive balances mean the group owes the member; negative balances mean the member owes the group. Balances are derived from non-deleted expenses and shares, never stored as a duplicate value, and sum exactly to `0.00`.
- Expenses are immutable. Only their payer may delete them. Deletion is a soft delete; an absent, already-deleted, or wrong-group expense returns `404`, while a non-payer returns `403`.
- Expense lists use `created_at DESC, id DESC`; deleted expenses are excluded.

### Idempotency

The idempotency scope is `(group_id, Idempotency-Key)` and will be enforced with a database unique constraint. New creation returns `201`; replay returns the original expense with `200`, including a deleted expense if that key's original expense was later soft-deleted. Keys remain reserved after deletion.

The request order is membership check, body validation, transactional insert attempt, then replay lookup after a unique-key conflict. Consequently, a malformed replay request still gets `422`, while a different valid request with the same key returns the original expense. This avoids a race-prone select-then-insert pre-check and keeps the database as the source of truth.

## Initial data

The deterministic seed data is:

- Users: `alice`, `bob`, `carol`, `dan`
- Group 1: `Chiang Mai trip` — alice, bob, carol
- Group 2: `Office lunch` — bob, dan

## Local setup

The backend runs only from `backend/.venv`; frontend dependencies are local to `frontend/node_modules`.

1. Copy `.env.example` to `.env` and set database credentials.
2. Create the backend environment with `python -m venv backend/.venv`.
3. Install backend packages with `backend/.venv/Scripts/python -m pip install -r backend/requirements-dev.txt`.
4. Install frontend packages with `npm install --prefix frontend`.
5. Run the API with `backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload`.
6. Run the frontend with `npm run dev --prefix frontend`.
7. Run backend tests with `backend/.venv/Scripts/python -m pytest -q backend/tests` and lint with `backend/.venv/Scripts/python -m ruff check backend`.
8. Run frontend lint with `npm run lint --prefix frontend`.

Migration and seed commands are added with the database setup.

## Known limitations and next steps

The initial required scope has no real authentication, pagination, settlement suggestions, repayments, Docker Compose, or expense editing. These are intentional exclusions until the required correctness and test coverage are complete.

