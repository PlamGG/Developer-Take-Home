from decimal import Decimal

from app.exceptions import (
    AuthenticationError,
    BusinessRuleError,
    ForbiddenError,
    NotFoundError,
)
from app.models import Expense, ExpenseShare, Group, User, group_members
from app.schemas import CreateExpenseRequest, ExpenseResponse, ExpenseShareResponse, SplitEqual
from app.services.money import (
    allocate_equal_shares,
    format_satang_to_amount,
    parse_amount_to_satang,
    validate_exact_shares,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def get_current_user(db: Session, x_user: str | None) -> User:
    if not x_user or not x_user.strip():
        raise AuthenticationError("Missing X-User header")
    user = db.scalar(select(User).where(User.username == x_user.strip()))
    if not user:
        raise AuthenticationError("Unknown user")
    return user


def get_group_with_access_check(db: Session, group_id: int, user: User) -> Group:
    group = db.scalar(select(Group).where(Group.id == group_id))
    if not group:
        raise NotFoundError("group_not_found", "Group not found")

    is_member = db.scalar(
        select(group_members.c.user_id).where(
            group_members.c.group_id == group_id, group_members.c.user_id == user.id
        )
    )
    if not is_member:
        raise ForbiddenError("not_a_member", "Not a member of this group")

    return group


def serialize_expense(expense: Expense, shares: list[tuple[str, str]]) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        group_id=expense.group_id,
        description=expense.description,
        paid_by=expense.payer.username,
        amount=format_satang_to_amount(int(round(float(expense.amount) * 100))),
        created_at=expense.created_at.isoformat().replace("+00:00", "Z"),
        deleted_at=expense.deleted_at.isoformat().replace("+00:00", "Z")
        if expense.deleted_at
        else None,
        shares=[ExpenseShareResponse(username=u, amount=a) for u, a in shares],
    )


def load_expense_response(db: Session, expense: Expense) -> ExpenseResponse:
    # Query shares ordered by id ASC
    db_shares = (
        db.execute(
            select(ExpenseShare, User.username)
            .join(User, ExpenseShare.user_id == User.id)
            .where(ExpenseShare.expense_id == expense.id)
            .order_by(ExpenseShare.id.asc())
        )
        .all()
    )
    shares = [
        (username, format_satang_to_amount(int(round(float(share.amount) * 100))))
        for share, username in db_shares
    ]
    return serialize_expense(expense, shares)


def create_expense(
    db: Session,
    group_id: int,
    requester: User,
    idempotency_key: str,
    payload: CreateExpenseRequest,
) -> tuple[ExpenseResponse, int]:
    # 1. Access check
    group = get_group_with_access_check(db, group_id, requester)

    # 2. Check Idempotency-Key header
    clean_key = idempotency_key.strip()
    if not clean_key or len(clean_key) > 255:
        raise BusinessRuleError("invalid_idempotency_key", "Invalid Idempotency-Key")

    # 3. Validate description
    clean_desc = payload.description.strip()
    if not clean_desc or len(clean_desc) > 200:
        raise BusinessRuleError("invalid_description", "Invalid description")

    # 4. Validate amount
    satang = parse_amount_to_satang(payload.amount)
    decimal_amount = Decimal(satang) / Decimal(100)

    # 5. Validate paid_by member
    payer = db.scalar(select(User).where(User.username == payload.paid_by))
    if not payer:
        raise BusinessRuleError("invalid_payer", "Payer does not exist")

    is_payer_member = db.scalar(
        select(group_members.c.user_id).where(
            group_members.c.group_id == group.id, group_members.c.user_id == payer.id
        )
    )
    if not is_payer_member:
        raise BusinessRuleError("invalid_payer", "Payer is not a member of the group")

    # 6. Validate split members & calculate shares
    group_users = db.execute(
        select(User.id, User.username).join(
            group_members, group_members.c.user_id == User.id
        ).where(group_members.c.group_id == group.id)
    ).all()
    username_to_id = {u.username: u.id for u in group_users}

    if isinstance(payload.split, SplitEqual):
        split_members = payload.split.members
        if len(split_members) != len(set(split_members)):
            raise BusinessRuleError("invalid_split", "Duplicate members in split")
        for m in split_members:
            if m not in username_to_id:
                raise BusinessRuleError("invalid_split", f"Member {m} is not in group")
        allocated_shares = allocate_equal_shares(payload.amount, split_members)
    else:
        exact_shares = payload.split.shares
        for m in exact_shares:
            if m not in username_to_id:
                raise BusinessRuleError("invalid_split", f"Member {m} is not in group")
        allocated_shares = validate_exact_shares(payload.amount, exact_shares)

    # 7. Transactional insert with idempotency catch
    savepoint = db.begin_nested()
    try:
        new_expense = Expense(
            group_id=group.id,
            payer_id=payer.id,
            description=clean_desc,
            amount=decimal_amount,
            idempotency_key=clean_key,
        )
        db.add(new_expense)
        db.flush()

        for uname, share_amt in allocated_shares:
            s_satang = parse_amount_to_satang(share_amt)
            share_decimal = Decimal(s_satang) / Decimal(100)
            db.add(
                ExpenseShare(
                    expense_id=new_expense.id,
                    user_id=username_to_id[uname],
                    amount=share_decimal,
                )
            )
        db.flush()
        savepoint.commit()
        db.commit()
        db.refresh(new_expense)
        return serialize_expense(new_expense, allocated_shares), 201

    except IntegrityError:
        savepoint.rollback()
        # Look up existing expense by (group_id, idempotency_key)
        existing = db.scalar(
            select(Expense).where(
                Expense.group_id == group.id, Expense.idempotency_key == clean_key
            )
        )
        if existing:
            return load_expense_response(db, existing), 200
        raise
