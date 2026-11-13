-- =====================================================================
-- Secret Santa — PostgreSQL schema (V1)
--
-- Rules the database itself enforces, so a bug in the app can't break them:
--   • nobody draws themselves, and each person gives and receives once per exchange
--   • only members of an exchange can be in its exclusions or its draw
--   • excluded pairs (e.g. couples) can never be assigned to each other
--   • one persistent wishlist per person, reused across exchanges
--
-- Anonymity (who bought what, who drew whom) is enforced in the API layer,
-- with help from the owner_wishlist_items view at the bottom.
--
-- Requires PostgreSQL 13+ (gen_random_uuid is built in).
-- =====================================================================

BEGIN;

-- ---------- Types ----------------------------------------------------

CREATE TYPE draw_status AS ENUM ('open', 'drawn', 'cancelled');
CREATE TYPE member_role AS ENUM ('organizer', 'co_organizer', 'member');  -- co_organizer is used in V2
CREATE TYPE rsvp_status AS ENUM ('invited', 'joined', 'declined');


-- ---------- People ---------------------------------------------------

CREATE TABLE users (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
    phone       text UNIQUE CHECK (phone ~ '^[0-9]{10,15}$'),  -- digits only, e.g. 254712345678
    email       text CHECK (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_contact_required CHECK (phone IS NOT NULL OR email IS NOT NULL)
);
-- Emails are unique regardless of case (Betty@x.com = betty@x.com)
CREATE UNIQUE INDEX users_email_unique ON users (lower(email));


-- ---------- Exchanges ------------------------------------------------

CREATE TABLE exchanges (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name           text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
    budget_kes     integer CHECK (budget_kes >= 0),
    exchange_date  date,
    join_by        timestamptz,                       -- draw runs automatically after this
    draw_status    draw_status NOT NULL DEFAULT 'open',
    drawn_at       timestamptz,
    -- Organizer options, e.g. {"hide_pairings_from_organizer": true,
    --                          "contact_visible_to_giver_only": true}
    settings       jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(settings) = 'object'),
    created_by     bigint NOT NULL REFERENCES users (id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT exchanges_join_by_before_exchange
        CHECK (join_by IS NULL OR exchange_date IS NULL OR join_by::date <= exchange_date),
    CONSTRAINT exchanges_drawn_at_matches_status
        CHECK ((draw_status = 'drawn') = (drawn_at IS NOT NULL))
);

CREATE TABLE memberships (
    exchange_id       bigint NOT NULL REFERENCES exchanges (id) ON DELETE CASCADE,
    user_id           bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role              member_role NOT NULL DEFAULT 'member',
    rsvp              rsvp_status NOT NULL DEFAULT 'invited',
    shipping_address  text,           -- only shown to the person who draws this member
    joined_at         timestamptz,
    PRIMARY KEY (exchange_id, user_id)
);
CREATE INDEX memberships_user_idx ON memberships (user_id);
-- Exactly one organizer per exchange (co-organizers are separate)
CREATE UNIQUE INDEX memberships_one_organizer
    ON memberships (exchange_id) WHERE role = 'organizer';

CREATE TABLE invitations (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exchange_id       bigint NOT NULL REFERENCES exchanges (id) ON DELETE CASCADE,
    token             uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),  -- goes in the invite link
    phone             text CHECK (phone ~ '^[0-9]{10,15}$'),
    email             text,
    channel           text NOT NULL CHECK (channel IN ('whatsapp', 'email')),
    invited_by        bigint NOT NULL REFERENCES users (id),
    sent_at           timestamptz,
    accepted_at       timestamptz,
    accepted_user_id  bigint REFERENCES users (id),
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT invitations_contact_required CHECK (phone IS NOT NULL OR email IS NOT NULL),
    CONSTRAINT invitations_channel_matches_contact CHECK (
        (channel = 'whatsapp' AND phone IS NOT NULL) OR (channel = 'email' AND email IS NOT NULL)
    ),
    CONSTRAINT invitations_accept_consistent
        CHECK ((accepted_at IS NULL) = (accepted_user_id IS NULL))
);
CREATE INDEX invitations_exchange_idx ON invitations (exchange_id);


-- ---------- Exclusions and the draw ----------------------------------

-- A mutual "these two can't draw each other" rule.
-- Pairs are stored in a fixed order (user_a < user_b), so (Ann, Bob) and (Bob, Ann)
-- can't both exist, and one row covers both directions.
CREATE TABLE exclusions (
    exchange_id  bigint NOT NULL,
    user_a       bigint NOT NULL,
    user_b       bigint NOT NULL,
    reason       text,                                   -- e.g. 'couple', 'same household'
    PRIMARY KEY (exchange_id, user_a, user_b),
    CHECK (user_a < user_b),
    -- Composite foreign keys: both people must be members of THIS exchange
    FOREIGN KEY (exchange_id, user_a) REFERENCES memberships (exchange_id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (exchange_id, user_b) REFERENCES memberships (exchange_id, user_id) ON DELETE CASCADE
);

-- The draw result: one row per giver.
CREATE TABLE assignments (
    exchange_id   bigint NOT NULL,
    giver_id      bigint NOT NULL,
    recipient_id  bigint NOT NULL,
    notified_at   timestamptz,                           -- when their WhatsApp/email went out
    PRIMARY KEY (exchange_id, giver_id),                 -- each person gives once
    UNIQUE (exchange_id, recipient_id),                  -- each person receives once
    CHECK (giver_id <> recipient_id),                    -- nobody draws themselves
    FOREIGN KEY (exchange_id, giver_id)     REFERENCES memberships (exchange_id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (exchange_id, recipient_id) REFERENCES memberships (exchange_id, user_id) ON DELETE CASCADE
);

-- Backstop: reject any assignment that breaks an exclusion,
-- even if the draw code has a bug.
CREATE FUNCTION assignments_respect_exclusions() RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM exclusions e
        WHERE e.exchange_id = NEW.exchange_id
          AND e.user_a = LEAST(NEW.giver_id, NEW.recipient_id)
          AND e.user_b = GREATEST(NEW.giver_id, NEW.recipient_id)
    ) THEN
        RAISE EXCEPTION 'Assignment % -> % breaks an exclusion in exchange %',
            NEW.giver_id, NEW.recipient_id, NEW.exchange_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER assignments_check_exclusions
    BEFORE INSERT OR UPDATE ON assignments
    FOR EACH ROW EXECUTE FUNCTION assignments_respect_exclusions();


-- ---------- Wishlists and gift help ----------------------------------

-- One wishlist per person, kept across every exchange they join.
CREATE TABLE wishlists (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     bigint NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE wishlist_items (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wishlist_id   bigint NOT NULL REFERENCES wishlists (id) ON DELETE CASCADE,
    title         text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 200),
    url           text CHECK (url ~* '^https?://'),     -- any store
    price_kes     numeric(10, 2) CHECK (price_kes >= 0),
    notes         text,
    priority      smallint NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3),  -- 1 = really want
    -- SECRET from the wishlist owner. Never return these two columns to the owner.
    purchased_by  bigint REFERENCES users (id) ON DELETE SET NULL,
    purchased_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT wishlist_items_purchase_consistent
        CHECK ((purchased_by IS NULL) = (purchased_at IS NULL))
);
CREATE INDEX wishlist_items_wishlist_idx ON wishlist_items (wishlist_id);

-- For people who won't build a wishlist.
CREATE TABLE questionnaires (
    user_id     bigint PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    sizes       jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(sizes) = 'object'),
                -- e.g. {"shirt": "M", "shoe": "39", "ring": "6"}
    likes       text,
    avoid       text,                                   -- e.g. 'no scented candles'
    updated_at  timestamptz NOT NULL DEFAULT now()
);


-- ---------- Privacy helpers ------------------------------------------

-- What the wishlist OWNER is allowed to see: no purchase information.
-- The "my wishlist" endpoint reads from this view, never from wishlist_items directly.
CREATE VIEW owner_wishlist_items AS
SELECT i.id, w.user_id AS owner_id, i.wishlist_id, i.title, i.url, i.price_kes,
       i.notes, i.priority, i.created_at
FROM wishlist_items i
JOIN wishlists w ON w.id = i.wishlist_id;

COMMIT;
