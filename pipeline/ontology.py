"""Ontology for the RPS pursuit-evasion sandbox.

A deliberately small class/instance taxonomy:

- ``AssetType`` — the three roles in the rock-paper-scissors cycle, plus the
  static ``beats`` relation that decides engagements.
- ``AssetClass`` — a *template* for a kind of asset: its type plus the
  kinematic/energy parameters shared by every instance of that class.
- ``Asset`` — a *concrete* instance placed on a team at an initial pose.

This module is pure Python (no gds / sympy imports). It is the shared
vocabulary consumed by the symbolic dynamics, the leaders, the engagement
rules, and the formal export.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class AssetType(str, Enum):
    """The three rock-paper-scissors roles."""

    ROCK = "rock"
    PAPER = "paper"
    SCISSORS = "scissors"

    @property
    def letter(self) -> str:
        return {"rock": "R", "paper": "P", "scissors": "S"}[self.value]


# Static dominance cycle: key beats value.
_BEATS: dict[AssetType, AssetType] = {
    AssetType.ROCK: AssetType.SCISSORS,
    AssetType.SCISSORS: AssetType.PAPER,
    AssetType.PAPER: AssetType.ROCK,
}


def beats(a: AssetType, b: AssetType) -> bool:
    """True iff an asset of type ``a`` destroys an asset of type ``b`` on contact."""
    return _BEATS[a] is b


def prey_of(t: AssetType) -> AssetType:
    """The type that ``t`` beats (the target an asset of type ``t`` hunts)."""
    return _BEATS[t]


def predator_of(t: AssetType) -> AssetType:
    """The type that beats ``t`` (the type an asset of type ``t`` flees)."""
    for predator, prey in _BEATS.items():
        if prey is t:
            return predator
    raise KeyError(t)  # unreachable for a well-formed cycle


@dataclass(frozen=True)
class AssetClass:
    """Template parameters shared by every instance of an asset class.

    Each class has its own kinematics, so the three types move differently — this
    asymmetry (together with asymmetric starting positions) spreads the action out
    across the arena instead of collapsing it to the centre. These per-class gains
    feed the symbolic field directly (see ``dynamics.py``), so they genuinely shape
    motion, not just engagements.

    The chase/flee saturations respect the rock-paper-scissors cycle: every
    predator's ``chase`` exceeds its prey's ``flee`` (rock>scissors, scissors>paper,
    paper>rock), so pursuits still terminate.

    Two radii: ``collision_radius`` is the asset's physical body (drawn 1:1 in the
    arena; two bodies overlapping = both destroyed), and ``kill_radius`` is the reach
    of a directional **kill cone** — an attacker destroys a prey-type enemy only if it
    lies within ``kill_radius`` AND within ``kill_half_angle`` of the attacker's
    heading.
    """

    name: str
    type: AssetType
    damping: float            # c in d2r/dt2 = control - c*v
    chase: float              # pursuit control saturation (agility toward target)
    flee: float               # evasion control saturation (agility away from predators)
    collision_radius: float   # physical body; bodies overlapping → both destroyed
    kill_radius: float        # reach of the directional kill cone (> collision_radius)
    kill_half_angle: float    # half-angle of the kill cone, radians, from heading
    attract_gain: float       # pull toward assigned target
    repel_gain: float         # push from predators
    glyph: str = ""

    def __post_init__(self) -> None:
        if not self.glyph:
            object.__setattr__(self, "glyph", self.type.letter)

    @property
    def engage_radius(self) -> float:
        """Preferred stand-off distance to a target: strike from cone reach,
        don't ram. Set just inside ``kill_radius`` (so the prey is in the cone but
        the attacker is already decelerating at strike range) and well outside the
        collision body."""
        return ENGAGE_FACTOR * self.kill_radius


# Fraction of kill_radius an attacker holds at while engaging.
ENGAGE_FACTOR = 0.8


# One class per type, deliberately asymmetric:
#   rock     — heavy, long reach, strong sluggish chaser
#   paper    — balanced
#   scissors — light, twitchy, quickest to flee but short reach
CLASSES: dict[str, AssetClass] = {
    "rock": AssetClass(
        name="rock", type=AssetType.ROCK, damping=0.7,
        chase=2.0, flee=1.0, collision_radius=0.45,
        kill_radius=1.7, kill_half_angle=math.radians(32),
        attract_gain=0.9, repel_gain=1.0),
    "paper": AssetClass(
        name="paper", type=AssetType.PAPER, damping=0.85,
        chase=1.9, flee=0.9, collision_radius=0.34,
        kill_radius=1.5, kill_half_angle=math.radians(45),
        attract_gain=1.2, repel_gain=1.4),
    "scissors": AssetClass(
        name="scissors", type=AssetType.SCISSORS, damping=1.0,
        chase=1.8, flee=0.8, collision_radius=0.3,
        kill_radius=1.3, kill_half_angle=math.radians(58),
        attract_gain=1.5, repel_gain=1.7),
}


@dataclass
class Asset:
    """A concrete asset instance in a game.

    ``active`` is the *admissible-action gate*: 1 while the asset can act, 0
    once destroyed (its admissible action space has collapsed to the empty set).
    """

    id: str
    class_name: str
    team: str
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    active: int = 1
    target_id: str | None = None

    @property
    def asset_class(self) -> AssetClass:
        return CLASSES[self.class_name]

    @property
    def type(self) -> AssetType:
        return self.asset_class.type


def ontology_summary() -> dict:
    """Serializable description of the taxonomy for the formal view."""
    return {
        "types": [
            {
                "name": t.value,
                "letter": t.letter,
                "beats": prey_of(t).value,
                "beaten_by": predator_of(t).value,
            }
            for t in AssetType
        ],
        "classes": [
            {
                "name": c.name,
                "type": c.type.value,
                "damping": c.damping,
                "chase": c.chase,
                "flee": c.flee,
                "collision_radius": c.collision_radius,
                "kill_radius": c.kill_radius,
                "kill_angle_deg": round(math.degrees(c.kill_half_angle)),
                "engage_radius": round(c.engage_radius, 2),
                "attract_gain": c.attract_gain,
                "repel_gain": c.repel_gain,
                "glyph": c.glyph,
            }
            for c in CLASSES.values()
        ],
        "admissibility_note": (
            "Each asset carries an admissible-action gate active_i in {0,1}. "
            "On a losing engagement the gate collapses to 0 (admissible action "
            "space = empty set): the asset applies no control thereafter."
        ),
        "interaction_rules": [
            "Kill cone (RPS): an attacker destroys a prey-type enemy that lies "
            "within its kill_radius AND within kill_half_angle of its heading. "
            "Directional — the attacker must be facing (and moving toward) the prey.",
            "Stand-off engagement: an attacker is pulled to engage_radius "
            "(≈0.8·kill_radius) from its target, not to contact — it strikes from "
            "cone reach and decelerates, so it usually survives the kill instead of "
            "ramming the fresh corpse.",
            "Collision: two asset bodies overlapping (distance <= sum of "
            "collision_radii) are BOTH destroyed — independent of type or team. "
            "This also resolves same-type standoffs.",
            "Hazard: a destroyed asset is a hazard; a live asset whose body overlaps "
            "a corpse is destroyed (the corpse persists).",
            "Personal space: a short-range repulsion from every visible body "
            "(alive OR corpse) except an asset's assigned target. Because we assume "
            "full observability, corpses are visible and so are avoided — this is "
            "the collision-avoidance drive that also steers assets around hazards. "
            "(A destroyed asset still REPELS, but no longer THREATENS: its "
            "predator-flee contribution is gated off.)",
        ],
    }


if __name__ == "__main__":  # tiny smoke check
    for t in AssetType:
        print(f"{t.letter} ({t.value}): beats {prey_of(t).value}, fears {predator_of(t).value}")
    assert beats(AssetType.ROCK, AssetType.SCISSORS)
    assert not beats(AssetType.ROCK, AssetType.PAPER)
    print("classes:", list(CLASSES))
