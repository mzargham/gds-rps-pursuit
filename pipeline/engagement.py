"""Engagement resolution — the discrete reset map between integration segments.

Three interaction rules, all evaluated against the pre-resolution snapshot, then
losses applied together:

1. **Kill cone** (RPS): an attacker destroys a prey-type *enemy* that lies within
   the attacker's ``kill_radius`` AND within ``kill_half_angle`` of the attacker's
   heading (its velocity direction). Directional — you must be facing and moving
   toward your prey to strike it. The attacker survives.
2. **Collision**: two asset *bodies* overlapping (distance ≤ sum of their
   ``collision_radius`` — i.e. the drawn circles touch) destroys **both**,
   independent of type or team. Resolves same-type standoffs and friendly crowding.
3. **Hazard**: a destroyed asset is a hazard. A live asset whose body overlaps a
   corpse is destroyed (the corpse persists).

All destruction is the same parameter flip on the symbolic field: ``active_i → 0``.
"""

from __future__ import annotations

import math

from ontology import Asset, beats

_HEADING_EPS = 1e-3  # below this speed an asset has no usable heading → cannot strike


def _dist(a: Asset, b: Asset) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _bodies_overlap(a: Asset, b: Asset) -> bool:
    return _dist(a, b) <= a.asset_class.collision_radius + b.asset_class.collision_radius


def _in_kill_cone(attacker: Asset, prey: Asset) -> bool:
    """True if ``prey`` is inside ``attacker``'s directional kill cone."""
    cls = attacker.asset_class
    dx, dy = prey.x - attacker.x, prey.y - attacker.y
    d = math.hypot(dx, dy)
    if d > cls.kill_radius or d < 1e-12:
        return False
    speed = math.hypot(attacker.vx, attacker.vy)
    if speed < _HEADING_EPS:
        return False  # no heading → no strike
    # angle between heading and the bearing to the prey
    cos_off = (attacker.vx * dx + attacker.vy * dy) / (speed * d)
    cos_off = max(-1.0, min(1.0, cos_off))
    return math.acos(cos_off) <= cls.kill_half_angle


def resolve_engagements(assets: list[Asset], t: float) -> list[dict]:
    """Apply kill cones + collisions + hazards in place; return the event list.

    Events carry a ``kind`` (``"rps"`` | ``"collision"`` | ``"hazard"``) plus the
    midpoint ``x, y`` for the arena animation.
    """
    snapshot = [(a, a.active) for a in assets]
    to_destroy: set[str] = set()
    events: list[dict] = []

    def mid(a: Asset, b: Asset) -> tuple[float, float]:
        return round(0.5 * (a.x + b.x), 4), round(0.5 * (a.y + b.y), 4)

    n = len(assets)
    for i in range(n):
        ai, ai_alive = snapshot[i]
        for j in range(i + 1, n):
            aj, aj_alive = snapshot[j]

            if ai_alive and aj_alive:
                # collision (any pair, bodies overlap) — both destroyed
                if _bodies_overlap(ai, aj):
                    to_destroy.add(ai.id)
                    to_destroy.add(aj.id)
                    mx, my = mid(ai, aj)
                    events.append({"t": round(t, 4), "kind": "collision",
                                   "a": ai.id, "b": aj.id, "x": mx, "y": my})
                    continue
                # kill cone (enemies): the type-superior attacker strikes if facing
                if ai.team != aj.team:
                    if beats(ai.type, aj.type) and _in_kill_cone(ai, aj):
                        to_destroy.add(aj.id)
                        mx, my = mid(ai, aj)
                        events.append({"t": round(t, 4), "kind": "rps",
                                       "winner": ai.id, "loser": aj.id, "x": mx, "y": my})
                    elif beats(aj.type, ai.type) and _in_kill_cone(aj, ai):
                        to_destroy.add(ai.id)
                        mx, my = mid(ai, aj)
                        events.append({"t": round(t, 4), "kind": "rps",
                                       "winner": aj.id, "loser": ai.id, "x": mx, "y": my})

            # one alive, one a corpse: the corpse is a hazard on body overlap
            elif ai_alive != aj_alive and _bodies_overlap(ai, aj):
                live, dead = (ai, aj) if ai_alive else (aj, ai)
                to_destroy.add(live.id)
                mx, my = mid(ai, aj)
                events.append({"t": round(t, 4), "kind": "hazard",
                               "victim": live.id, "hazard": dead.id, "x": mx, "y": my})

    by_id = {a.id: a for a in assets}
    for aid in to_destroy:
        by_id[aid].active = 0       # admissible action space → ∅
        by_id[aid].target_id = None
    return events


def survivors(assets: list[Asset]) -> dict[str, int]:
    """Count active assets per team."""
    counts: dict[str, int] = {}
    for a in assets:
        if a.active:
            counts[a.team] = counts.get(a.team, 0) + 1
    return counts
