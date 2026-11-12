from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import BusinessRuleError
from app.models import Group, User, group_members
from app.schemas import CreateExpenseRequest, ExpenseResponse, GroupResponse
from app.services.expense import create_expense, get_current_user, get_group_with_access_check

router = APIRouter()


@router.get("/groups", response_model=list[GroupResponse])
def list_groups(
    x_user: str | None = Header(None, alias="X-User"),
    db: Session = Depends(get_db),
) -> list[GroupResponse]:
    user = get_current_user(db, x_user)
    groups = (
        db.execute(
            select(Group)
            .join(group_members, group_members.c.group_id == Group.id)
            .where(group_members.c.user_id == user.id)
            .order_by(Group.id.asc())
        )
        .scalars()
        .all()
    )

    result = []
    for g in groups:
        members = (
            db.execute(
                select(User.username)
                .join(group_members, group_members.c.user_id == User.id)
                .where(group_members.c.group_id == g.id)
                .order_by(User.id.asc())
            )
            .scalars()
            .all()
        )
        result.append(GroupResponse(id=g.id, name=g.name, members=list(members)))
    return result


@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: int,
    x_user: str | None = Header(None, alias="X-User"),
    db: Session = Depends(get_db),
) -> GroupResponse:
    user = get_current_user(db, x_user)
    group = get_group_with_access_check(db, group_id, user)
    members = (
        db.execute(
            select(User.username)
            .join(group_members, group_members.c.user_id == User.id)
            .where(group_members.c.group_id == group.id)
            .order_by(User.id.asc())
        )
        .scalars()
        .all()
    )
    return GroupResponse(id=group.id, name=group.name, members=list(members))


@router.post(
    "/groups/{group_id}/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_group_expense(
    group_id: int,
    payload: CreateExpenseRequest,
    response: Response,
    x_user: str | None = Header(None, alias="X-User"),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> ExpenseResponse:
    user = get_current_user(db, x_user)
    if not idempotency_key or not idempotency_key.strip():
        raise BusinessRuleError("invalid_idempotency_key", "Idempotency-Key header is required")

    expense_resp, status_code = create_expense(db, group_id, user, idempotency_key, payload)
    response.status_code = status_code
    return expense_resp
