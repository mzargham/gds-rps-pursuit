"""Team leaders — the policy ``g`` that assigns tasks to assets.

A leader observes the *full* world state and returns a target assignment for its
own team's assets. The interface is deliberately rich: a future cooperative /
state-dependent policy gets everything it needs (all assets, types, positions,
liveness). v1 ships only naive leaders.

Assignment form (v1): ``{asset_id: target_id | None}``. The dynamics turn an
assignment into the ``w_ij`` task weights (a 0/1 indicator here; a richer policy
could return weighted / multi-target tasks and widen ``pack_params`` accordingly).
"""

from __future__ import annotations

import math
import random
from typing import Protocol

from ontology import Asset, beats


def _dist(a: Asset, b: Asset) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _alive_enemies(assets: list[Asset], team: str) -> list[Asset]:
    return [a for a in assets if a.team != team and a.active]


class Leader(Protocol):
    """A team leader: world state → task assignment for ``team``'s assets."""

    name: str

    def assign(self, assets: list[Asset], team: str) -> dict[str, str | None]:
        ...


class GreedyLeader:
    """Assign each asset to the nearest *beatable* enemy (its prey); else nearest enemy."""

    name = "greedy"

    def assign(self, assets: list[Asset], team: str) -> dict[str, str | None]:
        enemies = _alive_enemies(assets, team)
        out: dict[str, str | None] = {}
        for a in assets:
            if a.team != team or not a.active:
                continue
            prey = [e for e in enemies if beats(a.type, e.type)]
            pool = prey or enemies
            out[a.id] = min(pool, key=lambda e: _dist(a, e)).id if pool else None
        return out


class FixedLeader:
    """Use a static assignment from the instance config (alive assets only)."""

    name = "fixed"

    def __init__(self, assignments: dict[str, str | None]) -> None:
        self._assignments = dict(assignments)

    def assign(self, assets: list[Asset], team: str) -> dict[str, str | None]:
        by_id = {a.id: a for a in assets}
        out: dict[str, str | None] = {}
        for a in assets:
            if a.team != team or not a.active:
                continue
            tgt = self._assignments.get(a.id)
            # drop stale / dead targets
            if tgt is not None and (tgt not in by_id or not by_id[tgt].active):
                tgt = None
            out[a.id] = tgt
        return out


class RandomLeader:
    """Assign each asset a random alive enemy (seeded; prefers beatable prey)."""

    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def assign(self, assets: list[Asset], team: str) -> dict[str, str | None]:
        enemies = _alive_enemies(assets, team)
        out: dict[str, str | None] = {}
        for a in assets:
            if a.team != team or not a.active:
                continue
            prey = [e for e in enemies if beats(a.type, e.type)]
            pool = prey or enemies
            out[a.id] = self._rng.choice(pool).id if pool else None
        return out


def make_leader(spec: dict | str) -> Leader:
    """Build a leader from an instance-config spec (``"greedy"`` or a dict)."""
    if isinstance(spec, str):
        spec = {"type": spec}
    kind = spec["type"]
    if kind == "greedy":
        return GreedyLeader()
    if kind == "random":
        return RandomLeader(seed=int(spec.get("seed", 0)))
    if kind == "fixed":
        return FixedLeader(assignments=spec.get("assignments", {}))
    raise ValueError(f"unknown leader type: {kind!r}")
