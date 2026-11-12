# SplitBill

SplitBill is a production-grade shared-expense tracking application built with **FastAPI** (Python 3.12+), **Next.js** (TypeScript + Tailwind CSS), and **PostgreSQL 16**. It was engineered strictly under a contract-first, test-driven approach for the Chowpa Developer Take-Home Test.

---

## 1. Setup & Quickstart (Fresh Clone)

### Prerequisites
- Python 3.12+
- Node.js 20+ (with npm)
- Docker (or local/cloud PostgreSQL 16)

### Running PostgreSQL 16
Start a local PostgreSQL 16 container with a single command:
```bash
docker run --name splitbill-postgres -e POSTGRES_USER=splitbill -e POSTGRES_PASSWORD=splitbill -e POSTGRES_DB=splitbill -p 5432:5432 -d postgres:16
```

### Environment Configuration
Copy `.env.example` in both backend and frontend roots:
```bash
cp .env.example backend/.env
```
Ensure `backend/.env` points to your PostgreSQL instance:
```env
DATABASE_URL=postgresql+psycopg://splitbill:splitbill@localhost:5432/splitbill
TEST_DATABASE_URL=postgresql+psycopg://splitbill:splitbill@localhost:5432/splitbill_test
CORS_ORIGIN=http://localhost:3000
```

### Backend Setup & Commands
```bash
cd backend
python -m venv .venv

# Windows activation:
.venv\Scripts\activate
# Linux/macOS activation:
# source .venv/bin/activate

pip install -r requirements.txt -q

# Run migrations to head
alembic upgrade head

# Deterministic seed data (alice, bob, carol, dan & groups 1, 2)
python -m app.seed

# Run tests
pytest -q --tb=short

# Run linter & formatter check
ruff check .
ruff format --check .

# Start development API server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup & Commands
```bash
cd frontend
npm install --silent

# Run unit tests (shared test vectors)
node --test app/lib/money.test.ts

# Lint & build check
npm run lint
npm run build

# Start Next.js development server
npm run dev
```

---

## 2. Architecture & Contract Overview

The application strictly separates responsibilities into distinct layers:
- **Presentation & Routers (`app/routers.py`)**: Thin controllers handling HTTP requests, headers (`X-User`, `Idempotency-Key`), status codes, and Pydantic validation.
- **Domain & Services (`app/services/`)**: Pure business logic, strict decimal parsing/formatting (`app/services/money.py`), residual satang distribution algorithms, and transactional expense operations (`app/services/expense.py`).
- **Data Access & Persistence (`app/models.py`, `app/database.py`)**: Declarative SQLAlchemy models, explicit indexes, foreign keys, and check constraints (`amount > 0`, `amount >= 0`).

### API Endpoints

| Method | Endpoint | Success | Description |
|---|---|---|---|
| `GET` | `/groups` | `200` | List all groups where `X-User` is a member. |
| `GET` | `/groups/{group_id}` | `200` | Fetch group details and member usernames. |
| `POST` | `/groups/{group_id}/expenses` | `201` / `200` | Create an expense or replay idempotent submission. |
| `GET` | `/groups/{group_id}/expenses` | `200` | List non-deleted expenses ordered by `created_at DESC, id DESC`. |
| `DELETE` | `/groups/{group_id}/expenses/{expense_id}` | `204` | Soft-delete an expense (payer only). |
| `GET` | `/groups/{group_id}/balances` | `200` | Compute net zero-sum balances for all group members. |

### Error Payload Specification
All failures across the system (including authentication, business rules, and validation errors) adhere to a unified error shape:
```json
{
  "detail": {
    "code": "not_a_member",
    "message": "Not a member of this group"
  }
}
```

---

## 3. Key Design Decisions

### 403 Forbidden vs 404 for Non-Members
- **Decision:** Every group-scoped route executes checks in this exact order:
  1. `401 Unauthorized`: Missing or unrecognized `X-User`.
  2. `404 Not Found`: Group ID does not exist in the database.
  3. `403 Forbidden` (`not_a_member`): The user is valid but not a member of the group.
  4. `422 Unprocessable Entity`: Request body or business rule validation error.
- **Trade-off & Rationale:** Returning `403` deliberately leaks the fact that a group ID exists to non-members. In this shared-expense domain, group existence is not secret, whereas clear, debuggable permission diagnostics are significantly preferred by both users and reviewers over ambiguous `404` masks.

### Strict Monetary Representation & Arithmetic
- **Backend:** Monetary values are serialized and deserialized exclusively as strings with exactly two decimals (e.g., `"1000.00"`). The backend enforces the strict regex `^\d+(\.\d{1,2})?$`. In Python, all calculations use `Decimal` or integer satang; `float` is strictly prohibited. PostgreSQL persists amounts using `NUMERIC(12,2)`.
- **Frontend:** The frontend implements integer satang arithmetic (`frontend/app/lib/money.ts`). Float operations (`parseFloat`, `Number(x)`, `toFixed`) are completely avoided on monetary values to prevent IEEE 754 precision corruption (e.g., ensuring `0.1 + 0.2 = 0.30`).

### Residual Satang Allocation & Deterministic Member Order
- When splitting amounts equally that don't divide evenly into integers (e.g., `100.00 / 3`), residual satang (1 satang each) are awarded to members strictly in the order of `split.members`.
- **Frontend Locking Decision:** The frontend form always passes `split.members` and computes the live preview according to the group's canonical member order (as returned by `GET /groups/{id}`), regardless of the order in which the user checked checkboxes. This guarantees 100% deterministic agreement between the live preview and backend persistence.

### Idempotency Strategy & Concurrency Protection
- Enforced at the database level using a composite unique constraint `UNIQUE(group_id, idempotency_key)` on the `expenses` table.
- Transactions insert the expense and its shares inside a savepoint. If a concurrent duplicate or replay arrives, the database throws a unique constraint violation; the backend rolls back to the savepoint and retrieves the committed original expense, returning `200 OK`.
- **Check Order:** Membership and payload validation are executed **before** attempting idempotency replay. A malformed request with an existing key is rejected with `422`, while a valid replayed request returns the original expense.

---

## 4. Documented Assumptions

1. **Payer vs Requester:** The user making the request (`X-User`) must belong to the group, but `paid_by` can be any valid member of that group. A user may record an expense paid by a peer.
2. **Description Bounds:** `description` is trimmed of leading/trailing whitespace. It must be non-empty and have a length of at most 200 characters, failing with `422 invalid_description` otherwise.
3. **Exact Split Zero Shares:** In exact splits, members belonging to the group may be assigned `"0.00"`, provided all shares are non-negative and the sum matches the total amount exactly.
4. **Replay Payload Discrepancy:** If a client replays an `Idempotency-Key` with a valid but different payload, the API safely returns the originally created expense with `200 OK`.
5. **Key Reservation on Soft-Deletion:** Soft-deleted expenses retain their idempotency key (`deleted_at IS NOT NULL`). Replaying an idempotency key for a deleted expense returns the original expense with `200 OK` (including its `deleted_at` timestamp) and does not recreate a new expense.

---

## 5. Known Limitations & Production Next Steps

- **Authentication:** `X-User` header is used for scoping and demonstration. Production requires standard Bearer JWT / OAuth2 sessions.
- **Pagination:** Expense listing returns all non-deleted rows. High-volume systems require cursor-based pagination (`limit`, `before_id`).
- **Idempotency Payload Hash:** In production, a SHA-256 hash of the request body should be stored alongside the key. If a request arrives with the same key but differing payload hash, the server should return `409 Conflict`.
- **Idempotency Key TTL:** Unbounded unique keys accumulate over time. Production requires a TTL expiration (e.g., 24-48 hours) managed by Redis or a scheduled partition prune.
- **Materialized Balances / Snapshots:** Balances are currently calculated on the fly across all non-deleted expenses to ensure real-time zero-sum accuracy. For large groups with thousands of expenses, balance snapshots or materialized ledgers should be implemented.
- **Group Membership Lifecycle:** If group member deletion is introduced, the system must forbid removing any member whose net balance is not `0.00`, and membership records must be soft-deleted to maintain historical ledger consistency.

---

## 6. Approximate Time Log

| Milestone | Scope | Hours Spent | Notes |
|---|---|---|---|
| **Milestone 0** | API Contract & Specifications | 0.5h | Locked status codes, money schemas, and check order in README |
| **Milestone 1** | Project Scaffold & Tooling | 0.5h | Configured FastAPI, Next.js, Tailwind, Ruff, ESLint, pytest |
| **Milestone 2** | Database Foundation & Deterministic Seed | 0.5h | Configured SQLAlchemy 2.0, Alembic migration, and deterministic seed |
| **Milestone 3** | Pure Domain Logic & Unit Tests (TDD) | 1.0h | Implemented strict satang math, equal allocation, and shared test vectors |
| **Milestone 4** | Transactional & Idempotent Expense API | 1.0h | Implemented `POST /expenses` with savepoint conflict catching |
| **Milestone 5** | Remaining Endpoints & PostgreSQL Integration | 1.0h | Implemented list, balance, delete, and 17 acceptance tests |
| **Milestone 6** | Single-Page Frontend Workflow | 1.5h | Built Next.js UI, integer satang engine, and live preview |
| **Milestone 7** | Verification, Docs & AI Notes | 0.5h | Full test pass, linting, production build, and final documentation |
| **Total** | | **6.5h** | |
