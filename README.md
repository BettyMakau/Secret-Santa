# 🎁 Secret Santa

A small personal project: I wanted a Secret Santa for my friends with wishlists and WhatsApp reminders built in, and a good excuse to practise building a full-stack app from database to deployment.

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

## Data model (V1)

The full V1 schema is in [`db/schema.sql`](db/schema.sql). The app is being moved onto it step by step, and still runs on the simpler starter tables in `app/models.py` for now.

```
users            id, name, phone, email
exchanges        id, name, budget_kes, exchange_date, join_by, draw_status, settings (jsonb)
memberships      exchange_id, user_id, role, rsvp, shipping_address
invitations      exchange_id, token, phone/email, channel, accepted_at
exclusions       exchange_id, user_a, user_b        -- mutual "can't draw each other"
assignments      exchange_id, giver_id, recipient_id
wishlists        id, user_id                        -- one per person, kept across exchanges
wishlist_items   id, wishlist_id, title, url, price_kes, purchased_by (hidden from owner)
questionnaires   user_id, sizes, likes, avoid
```

Rules the database enforces on its own:

- Nobody draws themselves, and each person gives and receives exactly once per exchange.
- Only members of an exchange can appear in its exclusions or its draw (composite foreign keys).
- A trigger rejects any assignment that breaks an exclusion, even if the draw code has a bug.
- One organizer per exchange and one wishlist per person.
- The `owner_wishlist_items` view leaves out purchase columns, so the "my wishlist" endpoint can't leak who bought what.

To load it with sample data into an empty database:

```bash
psql -U santa -d secret_santa_dev -f db/schema.sql -f db/seed.sql
```

## The hard parts

1. **The draw is a constraint problem.** Nobody can draw themselves and exclusions must hold. Some exclusion sets have no valid answer, so the draw has to detect that and tell the organizer instead of retrying forever.
2. **Anonymity is enforced by the API, not just the UI.** Purchase markings are never sent to a wishlist's owner, and (in V2) anonymous questions never reveal who asked.

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

The tests run against the `TEST_DATABASE_URL` database (they drop its tables afterwards, so never point it at real data). They cover the draw logic, phone normalization, the full organizer → member flow, and every database rule in `db/schema.sql`.

## WhatsApp setup

By default `WHATSAPP_PROVIDER=console`, which logs messages to the terminal instead of sending them. That's handy for development and demos.

To send real messages:

1. Create an app at [developers.facebook.com](https://developers.facebook.com/) and add the WhatsApp product.
2. Copy the **access token** and **phone number ID** into `.env`, and set `WHATSAPP_PROVIDER=meta`.
3. Set `APP_BASE_URL` to the app's public URL so the links in messages work.

> Note: WhatsApp only allows free-form text to people who have messaged your business number in the last 24 hours. For cold outreach in production, register a message template and send that instead. The `wa.me` links on the organizer page work without any API setup.

## Roadmap

**V1 (for Christmas 2026):** invites, exclusions and the draw, WhatsApp notifications, wishlists with secret "I bought this" marking, and a gift questionnaire.

**V2:** anonymous Q&A between giver and recipient, co-organizers, repeating last year's exchange, reminders, and AI gift ideas.

The full plan with progress is in [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Project structure

```
app/
  __init__.py      app factory and config
  models.py        starter Group and Member tables
  draw.py          the draw algorithm
  whatsapp.py      phone normalization and message sending
  routes.py        organizer and member pages
  templates/       Jinja templates
  static/          CSS
tests/             pytest suite
db/
  schema.sql       V1 PostgreSQL schema
  seed.sql         sample data for local development
  init.sql         creates the test DB in Docker
docs/ROADMAP.md    V1 / V2 plan and progress
```
