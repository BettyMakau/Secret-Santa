-- Sample data for local development: run AFTER schema.sql.
--   psql -U santa -d secret_santa_dev -f db/schema.sql -f db/seed.sql
-- Four friends, one couple who mustn't draw each other, and some wishlist items.

BEGIN;

INSERT INTO users (name, phone, email) VALUES
    ('Betty',   '254712000001', 'betty@example.com'),
    ('Wanjiru', '254712000002', NULL),
    ('Otieno',  '254712000003', 'otieno@example.com'),
    ('Amani',   '254712000004', NULL);

INSERT INTO exchanges (name, budget_kes, exchange_date, join_by, created_by, settings)
SELECT 'Friends Christmas 2026', 2000, DATE '2026-12-20', TIMESTAMPTZ '2026-12-01 18:00+03', id,
       '{"hide_pairings_from_organizer": true, "contact_visible_to_giver_only": true}'
FROM users WHERE name = 'Betty';

INSERT INTO memberships (exchange_id, user_id, role, rsvp, joined_at)
SELECT e.id, u.id,
       CASE WHEN u.name = 'Betty' THEN 'organizer' ELSE 'member' END::member_role,
       'joined', now()
FROM exchanges e CROSS JOIN users u;

-- Otieno and Amani are a couple
INSERT INTO exclusions (exchange_id, user_a, user_b, reason)
SELECT e.id, LEAST(o.id, a.id), GREATEST(o.id, a.id), 'couple'
FROM exchanges e, users o, users a
WHERE o.name = 'Otieno' AND a.name = 'Amani';

INSERT INTO wishlists (user_id) SELECT id FROM users;

INSERT INTO wishlist_items (wishlist_id, title, url, price_kes, priority)
SELECT w.id, v.title, v.url, v.price, v.priority
FROM wishlists w JOIN users u ON u.id = w.user_id
JOIN (VALUES
    ('Wanjiru', 'Purple ceramic mug', NULL, 800, 1),
    ('Wanjiru', 'A novel by a Kenyan author', NULL, 1500, 2),
    ('Otieno',  'Running socks', 'https://example.com/socks', 1200, 1)
) AS v(name, title, url, price, priority) ON v.name = u.name;

INSERT INTO questionnaires (user_id, sizes, likes, avoid)
SELECT id, '{"shirt": "M", "shoe": "40"}', 'Football, coffee, board games', 'Scented candles'
FROM users WHERE name = 'Amani';

COMMIT;
