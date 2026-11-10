import random

import pytest

from app.draw import DrawError, make_assignments
from app.whatsapp import normalize_phone


@pytest.mark.parametrize("n", [3, 4, 7, 25])
def test_everyone_gives_and_receives_once(n):
    for seed in range(50):
        pairs = make_assignments(range(n), rng=random.Random(seed))
        assert set(pairs) == set(range(n))
        assert sorted(pairs.values()) == list(range(n))
        assert all(giver != recipient for giver, recipient in pairs.items())


def test_forms_a_single_loop():
    pairs = make_assignments(range(10), rng=random.Random(1))
    seen, current = set(), 0
    while current not in seen:
        seen.add(current)
        current = pairs[current]
    assert len(seen) == 10


@pytest.mark.parametrize("ids", [[], [1], [1, 2]])
def test_too_few_members(ids):
    with pytest.raises(DrawError):
        make_assignments(ids)


def test_duplicate_ids_rejected():
    with pytest.raises(DrawError):
        make_assignments([1, 1, 2])


@pytest.mark.parametrize("raw,expected", [
    ("0712 345 678", "254712345678"),
    ("+254-712-345678", "254712345678"),
    ("254712345678", "254712345678"),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "12345", "abc"])
def test_normalize_phone_rejects_bad_numbers(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)
