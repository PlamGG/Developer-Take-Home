# AI Notes & Engineering Transparency

This document details the AI tools utilized, engineering workflows, high-leverage prompts, unsafe suggestions detected and remediated, and the verification process followed throughout the SplitBill development lifecycle.

---

## 1. AI Tools & Workflow Roles

- **Gemini & Claude Code / Antigravity Agents**: Utilized for architectural decomposition, contract-first design, test generation, and cross-boundary validation between Python and TypeScript.
- **Workflow Model:** Contract-First and Test-Driven Development (TDD). 
  - API schemas and acceptance invariants were declared in `HANDOFF.md` and `README.md` prior to code generation.
  - Unit test vectors (`100.00/3`, `0.01/3`, `0.10/3`, `0.1 + 0.2`, `9999999999.99/2`) were drafted before implementing the money engine in both backend and frontend.
  - Strict incremental commits were enforced at each milestone boundary.

---

## 2. Effective Prompts & Directives

### Prompt 1: Strict Monetary Parsing & Zero-Float Enforcement
> *"Design a pure Python monetary allocation service that parses decimal string inputs into integer satang. Prohibit any conversion to float, float arithmetic, or scientific notation. If any non-string, NaN, Infinity, negative amount, or amount with more than 2 decimal places is provided, immediately raise a domain BusinessRuleError. Ensure residual satang are distributed one-by-one according to the explicit order of the input list."*
- **Outcome:** Produced an integer-based satang calculation engine in `app/services/money.py` completely immune to floating-point rounding bugs (`0.1 + 0.2 = 0.30`).

### Prompt 2: Transactional Idempotency with Concurrency Protection
> *"Implement expense creation in FastAPI such that idempotency is guarded at the database level via UNIQUE(group_id, idempotency_key). Do not rely on an application-level 'SELECT then INSERT' check, which is vulnerable to race conditions. Wrap the insertion in a database savepoint; on IntegrityError, rollback the savepoint, query the committed winner expense, and return 200 OK with the original payload."*
- **Outcome:** Guaranteed deterministic behavior under heavy concurrency without deadlocks, verified by multi-threaded integration tests (`test_concurrent_idempotent_expense_creation`).

---

## 3. Detected Unsafe / Incorrect AI Patterns & Corrections

During development, AI suggestions were systematically audited. Two critical unsafe patterns were detected and corrected:

### Case 1: Inadequate Soft-Delete Authorization Logic
- **The Issue:** The initial suggestion proposed a single conditional SQL update:
  ```sql
  UPDATE expenses SET deleted_at = NOW() 
  WHERE id = :id AND group_id = :group_id AND payer_id = :payer_id AND deleted_at IS NULL;
  ```
  While concise, checking `rowcount == 0` makes it impossible to distinguish between a non-existent/already deleted expense (`404 Not Found`) and an unauthorized deletion attempt by a non-payer (`403 Forbidden`).
- **Detection & Remediation:** Detected during milestone design review. The implementation was rewritten to first fetch the active expense in the group:
  1. If missing or `deleted_at IS NOT NULL` -> raise `404 Not Found`.
  2. If `expense.payer_id != requester.id` -> raise `403 Forbidden`.
  3. Otherwise, set `deleted_at` and return `204 No Content`.

### Case 2: Non-Deterministic Share Order from Unordered Relational Queries
- **The Issue:** When retrieving expenses from the database, AI omitted an explicit `ORDER BY` clause on child `expense_shares` queries, assuming relational engines preserve insertion order:
  ```python
  # Unsafe: relational tables do not guarantee insertion order
  shares = db.execute(select(ExpenseShare).where(ExpenseShare.expense_id == exp.id)).all()
  ```
  Under PostgreSQL parallel query plans or vacuum reorganizations, shares can return in arbitrary order, breaking the guarantee that residual satang match request order.
- **Detection & Remediation:** Caught during TDD test writing. Enforced `order_by(ExpenseShare.id.asc())` across all repository queries and serialized outputs.

### Case 3: Frontend Idempotency Key State Race
- **The Issue:** Suggested keeping a static or component-level random key that only changed on page load. If the user encountered a network timeout and clicked submit again, a new key would be generated, creating duplicate expenses instead of a safe retry. Conversely, if a submission succeeded, the key remained identical, causing subsequent distinct expenses to be treated as replays.
- **Remediation:** State machine was configured to preserve the active `Idempotency-Key` across retries during errors, while regenerating a fresh UUID immediately upon successful creation or whenever form input values are modified.

---

## 4. Verification & Review Protocol

Every milestone followed a non-negotiable review gate prior to committing:
1. **Automated Static Analysis:** `ruff check .` and `ruff format --check .` for Python; `eslint` and TypeScript type-checking for Next.js.
2. **Deterministic Test Verification:** `pytest -q --tb=short` executed against a real PostgreSQL instance for all integration tests, and Node.js native test runner executed for frontend unit tests.
3. **Clean Git Hygiene:** `git status` and `git diff` inspected prior to staging to ensure zero extraneous configuration files, virtual environments, or secret keys leaked into source control.
