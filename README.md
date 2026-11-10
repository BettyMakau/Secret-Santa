# 🎁 Secret Santa

A small web app for running a Secret Santa: create a group, add everyone's WhatsApp number, draw names, and each person gets a WhatsApp message with a private link showing who they're gifting and that person's wishlist.

**Stack:** Python 3.12 · Flask · SQLAlchemy · PostgreSQL · WhatsApp Cloud API · pytest · Docker

## Features

- **Random draw with no self-assignment.** Everyone is shuffled into a single loop and gives to the next person, so each person gives and receives exactly once.
- **Anonymous wishlists.** Each member edits their wishlist from their private link. Their Secret Santa sees it without either side knowing who the other is.
- **WhatsApp notifications.** One click messages every member their private link through the WhatsApp Cloud API. There's also a free `wa.me` click-to-chat link per member as a fallback.
- **Token links, no accounts.** The organizer gets a private admin link; each member gets their own private link.
- **Kenyan phone numbers handled.** `0712 345 678` and `+254-712-345678` both become `254712345678`.
- **Members lock after the draw**, duplicate phone numbers are rejected, and nobody gets messaged twice.

## How it works

```
Organizer                               Member
─────────                               ──────
/            create group
/g/<admin>   add members ─► draw ─► send WhatsApp ──► /m/<token>
                                                       • who you're gifting + their wishlist
                                                       • edit your own wishlist
```

| Table    | Key columns |
|----------|-------------|
| `group`  | `name`, `budget`, `exchange_date`, `admin_token`, `drawn_at` |
| `member` | `group_id → group`, `name`, `phone`, `wishlist`, `access_token`, `recipient_id → member`, `notified_at` |

## Run it locally

### Option A — Docker (easiest)

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:8000. Postgres runs in its own container, and both the app database and the test database are created for you.

### Option B — Python + your own PostgreSQL

1. Create the databases in PostgreSQL:
   ```sql
   CREATE USER santa WITH PASSWORD 'santa' CREATEDB;
   CREATE DATABASE secret_santa OWNER santa;
   CREATE DATABASE secret_santa_test OWNER santa;
   ```
2. Set up and run the app:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
   pip install -r requirements-dev.txt
   copy .env.example .env          # macOS/Linux: cp .env.example .env
   python run.py
   ```

Open http://127.0.0.1:5000. Tables are created automatically on first run.

## Tests

```bash
pytest
```

The tests run against the `TEST_DATABASE_URL` database (they drop its tables afterwards, so never point it at real data). They cover the draw logic, phone normalization and the full organizer → member flow.

## WhatsApp setup

By default `WHATSAPP_PROVIDER=console`, which logs messages to the terminal instead of sending them. That's handy for development and demos.

To send real messages:

1. Create an app at [developers.facebook.com](https://developers.facebook.com/) and add the WhatsApp product.
2. Copy the **access token** and **phone number ID** into `.env`, and set `WHATSAPP_PROVIDER=meta`.
3. Set `APP_BASE_URL` to the app's public URL so the links in messages work.

> Note: WhatsApp only allows free-form text to people who have messaged your business number in the last 24 hours. For cold outreach in production, register a message template and send that instead. The `wa.me` links on the organizer page work without any API setup.

## Roadmap

- [ ] CSRF protection (Flask-WTF) and rate limiting
- [ ] Exclusion rules (e.g. couples can't draw each other)
- [ ] Alembic migrations
- [ ] Reminder messages before the exchange date
- [ ] Deploy (Render / Railway) with CI running the tests on every push
- [ ] Optional organizer login, so the organizer can't open members' links

## Project structure

```
app/
  __init__.py      app factory and config
  models.py        Group and Member tables
  draw.py          the draw algorithm
  whatsapp.py      phone normalization and message sending
  routes.py        organizer and member pages
  templates/       Jinja templates
  static/          CSS
tests/             pytest suite
db/init.sql        creates the test DB in Docker
```
