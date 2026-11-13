"""Checks that db/schema.sql enforces the rules itself, independent of the app code.

Each test loads the schema + seed data into a throwaway Postgres schema (namespace)
in the test database, then drops it afterwards.
"""
import os
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import errors

DB_DIR = Path(__file__).resolve().parent.parent / "db"
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://santa:santa@localhost:5432/secret_santa_test",
).replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture
def db():
    ns = f"schema_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {ns}")
        conn.execute(f"SET search_path TO {ns}")
        conn.execute((DB_DIR / "schema.sql").read_text())
        conn.execute((DB_DIR / "seed.sql").read_text())
        try:
            yield conn
        finally:
            conn.execute(f"DROP SCHEMA {ns} CASCADE")


def ids(conn):
    """{'Betty': 1, ...} and the seeded exchange id."""
    people = dict(conn.execute("SELECT name, id FROM users").fetchall())
    exchange_id = conn.execute("SELECT id FROM exchanges").fetchone()[0]
    return people, exchange_id


def assign(conn, exchange_id, giver, recipient):
    conn.execute(
        "INSERT INTO assignments (exchange_id, giver_id, recipient_id) VALUES (%s, %s, %s)",
        (exchange_id, giver, recipient),
    )


def test_valid_draw_is_accepted(db):
    p, ex = ids(db)
    # Betty → Otieno → Wanjiru → Amani → Betty (the couple Otieno/Amani never meet)
    for giver, recipient in [("Betty", "Otieno"), ("Otieno", "Wanjiru"),
                             ("Wanjiru", "Amani"), ("Amani", "Betty")]:
        assign(db, ex, p[giver], p[recipient])
    assert db.execute("SELECT count(*) FROM assignments").fetchone()[0] == 4


def test_nobody_draws_themselves(db):
    p, ex = ids(db)
    with pytest.raises(errors.CheckViolation):
        assign(db, ex, p["Betty"], p["Betty"])


def test_each_person_gives_once(db):
    p, ex = ids(db)
    assign(db, ex, p["Betty"], p["Wanjiru"])
    with pytest.raises(errors.UniqueViolation):
        assign(db, ex, p["Betty"], p["Otieno"])


def test_each_person_receives_once(db):
    p, ex = ids(db)
    assign(db, ex, p["Betty"], p["Wanjiru"])
    with pytest.raises(errors.UniqueViolation):
        assign(db, ex, p["Otieno"], p["Wanjiru"])


@pytest.mark.parametrize("giver,recipient", [("Otieno", "Amani"), ("Amani", "Otieno")])
def test_exclusions_block_both_directions(db, giver, recipient):
    p, ex = ids(db)
    with pytest.raises(errors.CheckViolation, match="breaks an exclusion"):
        assign(db, ex, p[giver], p[recipient])


def test_exclusion_pairs_are_stored_once(db):
    p, ex = ids(db)
    hi, lo = max(p["Betty"], p["Wanjiru"]), min(p["Betty"], p["Wanjiru"])
    with pytest.raises(errors.CheckViolation):
        db.execute("INSERT INTO exclusions (exchange_id, user_a, user_b) VALUES (%s, %s, %s)",
                   (ex, hi, lo))


def test_only_members_can_be_drawn(db):
    p, ex = ids(db)
    outsider = db.execute(
        "INSERT INTO users (name, phone) VALUES ('Outsider', '254799999999') RETURNING id"
    ).fetchone()[0]
    with pytest.raises(errors.ForeignKeyViolation):
        assign(db, ex, p["Betty"], outsider)


def test_one_organizer_per_exchange(db):
    p, ex = ids(db)
    with pytest.raises(errors.UniqueViolation):
        db.execute("UPDATE memberships SET role = 'organizer' WHERE user_id = %s", (p["Wanjiru"],))


def test_one_wishlist_per_person(db):
    p, _ = ids(db)
    with pytest.raises(errors.UniqueViolation):
        db.execute("INSERT INTO wishlists (user_id) VALUES (%s)", (p["Betty"],))


def test_owner_view_hides_purchases(db):
    p, _ = ids(db)
    db.execute(
        "UPDATE wishlist_items SET purchased_by = %s, purchased_at = now() "
        "WHERE title = 'Purple ceramic mug'", (p["Betty"],))
    columns = [c.name for c in db.execute("SELECT * FROM owner_wishlist_items LIMIT 0").description]
    assert "purchased_by" not in columns and "purchased_at" not in columns
    rows = db.execute("SELECT title FROM owner_wishlist_items WHERE owner_id = %s",
                      (p["Wanjiru"],)).fetchall()
    assert ("Purple ceramic mug",) in rows


def test_purchase_fields_go_together(db):
    with pytest.raises(errors.CheckViolation):
        db.execute("UPDATE wishlist_items SET purchased_at = now() WHERE title = 'Running socks'")


def test_users_need_a_way_to_be_contacted(db):
    with pytest.raises(errors.CheckViolation):
        db.execute("INSERT INTO users (name) VALUES ('No Contact')")


def test_emails_are_unique_ignoring_case(db):
    with pytest.raises(errors.UniqueViolation):
        db.execute("INSERT INTO users (name, email) VALUES ('Dup', 'BETTY@example.com')")


def test_whatsapp_invite_needs_a_phone(db):
    p, ex = ids(db)
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "INSERT INTO invitations (exchange_id, email, channel, invited_by) "
            "VALUES (%s, 'x@example.com', 'whatsapp', %s)", (ex, p["Betty"]))
