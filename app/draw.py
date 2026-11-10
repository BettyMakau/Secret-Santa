"""The Secret Santa draw.

Shuffle everyone into a random circle and have each person give to the next.
This guarantees nobody draws themselves, and everyone gives and receives exactly once.
"""
import random
from typing import Hashable, Sequence

MIN_MEMBERS = 3


class DrawError(ValueError):
    pass


def make_assignments(
    member_ids: Sequence[Hashable], rng: random.Random | None = None
) -> dict:
    """Return {giver_id: recipient_id}."""
    ids = list(member_ids)
    if len(set(ids)) != len(ids):
        raise DrawError("Member IDs must be unique.")
    if len(ids) < MIN_MEMBERS:
        raise DrawError(f"You need at least {MIN_MEMBERS} members to draw.")

    rng = rng or random.SystemRandom()
    rng.shuffle(ids)
    return {ids[i]: ids[(i + 1) % len(ids)] for i in range(len(ids))}
