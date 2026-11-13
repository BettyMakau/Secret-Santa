# Roadmap

Goal: a working version my friends can use for Christmas 2026 (about six weeks), then grow it in small, visible commits.

Features are modelled on how popular gift-exchange apps work, rebuilt from scratch with my own names, wording and design.

## V1 — ready for December

| # | Feature | Notes | Status |
|---|---------|-------|--------|
| 1 | **PostgreSQL schema** | Users, exchanges, memberships, invitations, exclusions, assignments, wishlists, questionnaires. Rules enforced in the database. See [`db/schema.sql`](../db/schema.sql). | ✅ Done |
| 2 | **Invites** | Organizer sets name, budget, event date and join-by date, then invites by WhatsApp or email. Each invite carries a unique token link. | ⬜ |
| 3 | **Exclusions** | Mutual "can't draw each other" pairs, e.g. couples. | ⬜ |
| 4 | **The draw** | Run now, or automatically at the join-by date. Respects exclusions; detects impossible setups and tells the organizer instead of looping forever. Organizer can redo it if someone drops out. | ⬜ |
| 5 | **WhatsApp notifications** | Each giver gets their private link. Email as a fallback. | 🟡 Starter version works |
| 6 | **My Wishlist** | One persistent wishlist per person, reused across exchanges, items from any store. | 🟡 Starter version (single text box) |
| 7 | **Secret "I bought this"** | A giver marks an item as bought; the owner never sees it. | ⬜ |
| 8 | **Gift questionnaire** | Sizes, likes and things to avoid, for people who won't make a wishlist. | ⬜ |
| 9 | **Privacy defaults** | Pairings hidden from the organizer so they can play too; a member's address and contact are only visible to the person who drew them. | 🟡 Pairings hidden on organizer page |
| — | **Hardening** | CSRF protection, rate limiting, Alembic migrations. | ⬜ |
| — | **Deploy** | Render or Railway, with GitHub Actions running the tests on every push. | ⬜ |

## V2 — after launch

- **Anonymous Q&A** between a giver and their recipient only (never to anyone else; the asker is never revealed). Adds a `questions` table.
- **Co-organizers** (the `co_organizer` role already exists in the schema).
- **Repeat last year's exchange**, with an option to avoid drawing the same person as last year.
- **Reminders** before the join-by and exchange dates.
- **Gift tracking** (shipped / received).
- **AI gift ideas** from the questionnaire, interests and budget, using an LLM call.

## Not building

- **Social features:** activity feed, forums, group chat, messages to anyone other than your draw, shared group lists.
- **Skipped for now:** gift shop and affiliate links, White Elephant mode, multiple languages, native mobile apps.

## The hard parts (worth explaining in interviews)

1. **The draw is a constraint problem.** Nobody can draw themselves and exclusions must hold. Shuffle-and-retry is fine for small groups, but some exclusion sets have no valid answer (for example, three people where everyone excludes everyone). The draw has to detect that and say so, rather than loop forever. The database adds a backstop: a trigger rejects any assignment that breaks an exclusion.
2. **Anonymity is enforced by the API, not just hidden in the UI.** The "my wishlist" endpoint reads from the `owner_wishlist_items` view, which has no purchase columns, so `purchased_by` can never leak to the owner. Q&A endpoints (V2) must never return who asked.
