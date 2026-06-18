"""Kill-cone / collision / hazard resolution tests.

Bodies (collision_radius): rock 0.45, paper 0.34, scissors 0.3 → a pair collides
when distance ≤ sum. Kill radii: rock 1.3, paper 1.15, scissors 1.0; kill half-angle
rock 32°, scissors 58°.
"""

from __future__ import annotations

from engagement import resolve_engagements, survivors
from leaders import GreedyLeader
from ontology import Asset, AssetType, beats


def test_beats_cycle():
    assert beats(AssetType.ROCK, AssetType.SCISSORS)
    assert beats(AssetType.SCISSORS, AssetType.PAPER)
    assert beats(AssetType.PAPER, AssetType.ROCK)
    assert not beats(AssetType.SCISSORS, AssetType.ROCK)


def test_kill_cone_strikes_prey_when_facing():
    # rock heading +x toward scissors directly ahead, within kill_radius 1.3
    rock = Asset("b0", "rock", "blue", 0.0, 0.0, vx=1.0, vy=0.0)
    sci = Asset("r0", "scissors", "red", 1.0, 0.0)
    events = resolve_engagements([rock, sci], t=0.0)
    assert rock.active == 1 and sci.active == 0
    assert len(events) == 1 and events[0]["kind"] == "rps"
    assert events[0]["winner"] == "b0" and events[0]["loser"] == "r0"


def test_kill_cone_misses_prey_off_heading():
    # prey within kill_radius but 90° off the rock's heading → no strike
    rock = Asset("b0", "rock", "blue", 0.0, 0.0, vx=1.0, vy=0.0)
    sci = Asset("r0", "scissors", "red", 0.0, 1.0)   # straight up; heading is +x
    assert resolve_engagements([rock, sci], t=0.0) == []
    assert rock.active == 1 and sci.active == 1


def test_kill_cone_needs_a_heading():
    # a stationary attacker (no heading) cannot strike even with prey dead-ahead
    rock = Asset("b0", "rock", "blue", 0.0, 0.0, vx=0.0, vy=0.0)
    sci = Asset("r0", "scissors", "red", 0.9, 0.0)
    assert resolve_engagements([rock, sci], t=0.0) == []
    assert sci.active == 1


def test_collision_destroys_both_on_body_overlap():
    # same type → no kill cone; bodies overlap (d 0.5 < 0.45+0.45) → both die
    a = Asset("b0", "rock", "blue", 0.0, 0.0, vx=1.0, vy=0.0)
    b = Asset("r0", "rock", "red", 0.5, 0.0, vx=-1.0, vy=0.0)
    events = resolve_engagements([a, b], t=0.0)
    assert a.active == 0 and b.active == 0
    assert len(events) == 1 and events[0]["kind"] == "collision"


def test_collision_kills_allies_too():
    a = Asset("b0", "rock", "blue", 0.0, 0.0)
    b = Asset("b1", "scissors", "blue", 0.5, 0.0)   # d 0.5 < 0.45+0.30
    resolve_engagements([a, b], t=0.0)
    assert a.active == 0 and b.active == 0


def test_allies_in_kill_cone_are_safe():
    # rock facing an ally scissors within kill_radius, but bodies not overlapping
    rock = Asset("b0", "rock", "blue", 0.0, 0.0, vx=1.0, vy=0.0)
    ally = Asset("b1", "scissors", "blue", 1.0, 0.0)   # d 1.0 > 0.75 (no collision)
    assert resolve_engagements([rock, ally], t=0.0) == []
    assert rock.active == 1 and ally.active == 1


def test_corpse_is_a_hazard_on_body_overlap():
    live = Asset("r0", "scissors", "red", 0.0, 0.0, vx=0.0, vy=1.0)
    corpse = Asset("b0", "rock", "blue", 0.5, 0.0, active=0)   # d 0.5 < 0.3+0.45
    events = resolve_engagements([live, corpse], t=0.0)
    assert live.active == 0 and corpse.active == 0
    assert len(events) == 1 and events[0]["kind"] == "hazard"
    assert events[0]["victim"] == "r0" and events[0]["hazard"] == "b0"


def test_no_contact_no_effect():
    a = Asset("b0", "rock", "blue", 0.0, 0.0, vx=1.0, vy=0.0)
    b = Asset("r0", "scissors", "red", 5.0, 5.0)
    assert resolve_engagements([a, b], t=0.0) == []
    assert survivors([a, b]) == {"blue": 1, "red": 1}


def test_greedy_leader_targets_nearest_prey():
    rock = Asset("b0", "rock", "blue", 0.0, 0.0)
    near_sci = Asset("r0", "scissors", "red", 1.0, 0.0)
    far_sci = Asset("r1", "scissors", "red", 9.0, 0.0)
    paper = Asset("r2", "paper", "red", 0.5, 0.0)
    out = GreedyLeader().assign([rock, near_sci, far_sci, paper], "blue")
    assert out["b0"] == "r0"
