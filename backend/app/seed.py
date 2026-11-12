"""Deterministic development seed data for SplitBill."""

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Group, User, group_members

USERS = ((1, "alice"), (2, "bob"), (3, "carol"), (4, "dan"))
GROUPS = ((1, "Chiang Mai trip"), (2, "Office lunch"))
MEMBERSHIPS = ((1, 1), (1, 2), (1, 3), (2, 2), (2, 4))


def seed(session: Session) -> None:
    """Upsert the required users, groups, memberships, and reset serial sequences."""
    for user_id, username in USERS:
        statement = insert(User).values(id=user_id, username=username)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[User.id], set_={"username": statement.excluded.username}
            )
        )

    for group_id, name in GROUPS:
        statement = insert(Group).values(id=group_id, name=name)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Group.id], set_={"name": statement.excluded.name}
            )
        )

    for group_id, user_id in MEMBERSHIPS:
        session.execute(
            insert(group_members)
            .values(group_id=group_id, user_id=user_id)
            .on_conflict_do_nothing(index_elements=["group_id", "user_id"])
        )

    for table_name in ("users", "groups"):
        session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                "(SELECT MAX(id) FROM " + table_name + "), true)"
            ),
            {"table_name": table_name},
        )


def main() -> None:
    """Seed the configured database from the command line."""
    with SessionLocal.begin() as session:
        seed(session)


if __name__ == "__main__":
    main()
