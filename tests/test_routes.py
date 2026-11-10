import os

import pytest

from app import create_app
from app.models import Group, Member, db

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://santa:santa@localhost:5432/secret_santa_test",
)


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": TEST_DATABASE_URL,
        "WHATSAPP_PROVIDER": "console",
        "APP_BASE_URL": "https://santa.test",
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_group(client, n_members=3):
    resp = client.post("/groups", data={"name": "Office 2026", "budget": "KES 1,500"})
    admin_url = resp.headers["Location"]
    for i in range(n_members):
        client.post(f"{admin_url}/members", data={"name": f"Person {i}", "phone": f"07120000{i:02d}"})
    return admin_url


def test_full_flow(app, client):
    admin_url = make_group(client, 4)

    with app.app_context():
        group = Group.query.one()
        assert len(group.members) == 4
        assert group.members[0].phone == "254712000000"

    resp = client.post(f"{admin_url}/draw", follow_redirects=True)
    assert b"Names drawn" in resp.data

    with app.app_context():
        members = Member.query.all()
        assert all(m.recipient and m.recipient.id != m.id for m in members)
        tokens = {m.access_token: m.recipient.name for m in members}
        first = members[0]
        giver = next(m for m in members if m.recipient_id == first.id)
        first_token, giver_token = first.access_token, giver.access_token

    # A member sees who they're gifting
    token, recipient_name = next(iter(tokens.items()))
    page = client.get(f"/m/{token}")
    assert recipient_name.encode() in page.data

    # Wishlists are visible to the santa
    client.post(f"/m/{first_token}", data={"wishlist": "A purple mug"})
    assert b"A purple mug" in client.get(f"/m/{giver_token}").data

    # Notify everyone (console provider)
    resp = client.post(f"{admin_url}/notify", follow_redirects=True)
    assert b"Sent 4 WhatsApp message" in resp.data
    with app.app_context():
        assert all(m.notified_at for m in Member.query.all())

    # Notifying again doesn't resend
    resp = client.post(f"{admin_url}/notify", follow_redirects=True)
    assert b"already been notified" in resp.data


def test_cannot_draw_with_two_members(app, client):
    admin_url = make_group(client, 2)
    resp = client.post(f"{admin_url}/draw", follow_redirects=True)
    assert b"at least 3" in resp.data


def test_members_locked_after_draw(app, client):
    admin_url = make_group(client, 3)
    client.post(f"{admin_url}/draw")
    resp = client.post(f"{admin_url}/members", data={"name": "Late", "phone": "0712999999"},
                       follow_redirects=True)
    assert b"can&#39;t add members" in resp.data


def test_duplicate_phone_rejected(app, client):
    admin_url = make_group(client, 1)
    resp = client.post(f"{admin_url}/members", data={"name": "Dup", "phone": "+254 712 000 000"},
                       follow_redirects=True)
    assert b"already in the group" in resp.data


def test_admin_page_does_not_reveal_pairings(app, client):
    admin_url = make_group(client, 3)
    client.post(f"{admin_url}/draw")
    page = client.get(admin_url).data.decode()
    # The member page's "You're gifting" card must never appear on the organizer page
    assert 'class="big"' not in page


def test_unknown_tokens_404(client):
    assert client.get("/g/nope").status_code == 404
    assert client.get("/m/nope").status_code == 404
