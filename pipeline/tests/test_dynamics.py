"""Binding integrity + field-behavior tests for the symbolic dynamics.

The headline test (``test_lambdified_matches_reference``) proves the running
simulation reflects the formalism: the lambdified-once field equals an
independent hand-coded re-implementation on random states/params.
"""

from __future__ import annotations

import random

import pytest

from dynamics import Dynamics, FieldParams
from ontology import Asset


def make_roster() -> list[Asset]:
    # Blue rock chases red scissors; red scissors flees blue rock. A red paper too.
    return [
        Asset(id="b0", class_name="rock", team="blue", x=2.0, y=2.0),
        Asset(id="r0", class_name="scissors", team="red", x=6.0, y=6.0),
        Asset(id="r1", class_name="paper", team="red", x=9.0, y=3.0),
    ]


def _zero(params, gain):
    """Zero a per-asset gain across all assets (to isolate one drive in a test)."""
    for k in list(params):
        if k.startswith(f"{gain}_"):
            params[k] = 0.0


def test_lambdified_matches_reference():
    """sim == formalism: the lambdified field equals the hand-coded field."""
    assets = make_roster()
    dyn = Dynamics(assets)
    rng = random.Random(7)
    for _ in range(200):
        for a in assets:
            a.active = rng.choice([0, 1])
            enemies = [b.id for b in assets if b.team != a.team]
            a.target_id = rng.choice(enemies + [None])
        params = dyn.pack_params(assets, FieldParams())
        y = [rng.uniform(0.0, 16.0) for _ in range(4 * len(assets))]
        lamb = dyn.rhs(0.0, y, params)
        ref = dyn.reference_rhs(0.0, y, params)
        assert len(lamb) == len(ref) == 4 * len(assets)
        for a_, b_ in zip(lamb, ref, strict=True):
            assert a_ == pytest.approx(b_, abs=1e-9)


def test_attracted_to_assigned_target():
    """An asset accelerates toward the target the leader assigned it."""
    assets = make_roster()
    dyn = Dynamics(assets)
    assets[0].target_id = "r0"   # blue rock tasked to pursue red scissors at (6,6)
    assets[0].active = 1
    assets[1].active = 1
    assets[2].active = 0         # ignore the paper for this test
    params = dyn.pack_params(assets, FieldParams(k_wall=0.0, k_space=0.0))
    _zero(params, "k_r")         # attraction only
    y = [2, 2, 0, 0, 6, 6, 0, 0, 9, 3, 0, 0]
    d = dyn.rhs(0.0, y, params)
    ax0, ay0 = d[2], d[3]
    assert ax0 > 0 and ay0 > 0


def test_repelled_by_predator():
    """An asset accelerates away from an enemy that beats it."""
    assets = make_roster()
    dyn = Dynamics(assets)
    for a in assets:
        a.active = 1
        a.target_id = None
    assets[2].active = 0         # isolate the b0/r0 pair
    params = dyn.pack_params(assets, FieldParams(k_wall=0.0, k_space=0.0))
    _zero(params, "k_a")         # predator-flee only
    # b0 (rock) at (2,2), r0 (scissors) at (3,3): r0 flees toward (+,+)
    y = [2, 2, 0, 0, 3, 3, 0, 0, 9, 3, 0, 0]
    d = dyn.rhs(0.0, y, params)
    ax_r0, ay_r0 = d[4 * 1 + 2], d[4 * 1 + 3]
    assert ax_r0 > 0 and ay_r0 > 0


def test_inactive_asset_has_no_control_and_no_influence():
    """active_i = 0 ⇒ asset i applies no control AND exerts no force on others."""
    assets = [
        Asset(id="b0", class_name="rock", team="blue", x=2.0, y=2.0),
        Asset(id="r0", class_name="scissors", team="red", x=3.0, y=3.0),
    ]
    dyn = Dynamics(assets)
    y = [2, 2, 0, 0, 3, 3, 0, 0]

    # k_space=0 isolates the predator threat (which IS gated by active)
    params_live = dyn.pack_params(assets, FieldParams(k_wall=0.0, k_space=0.0))
    _zero(params_live, "k_a")
    d_live = dyn.rhs(0.0, y, params_live)
    r0_acc_live = (d_live[6], d_live[7])

    # destroy b0 → no control of its own, and no predator threat to r0
    assets[0].active = 0
    params_dead = dyn.pack_params(assets, FieldParams(k_wall=0.0, k_space=0.0))
    _zero(params_dead, "k_a")
    d_dead = dyn.rhs(0.0, y, params_dead)
    assert d_dead[2] == pytest.approx(0.0) and d_dead[3] == pytest.approx(0.0)
    assert d_dead[6] == pytest.approx(0.0, abs=1e-9)
    assert d_dead[7] == pytest.approx(0.0, abs=1e-9)
    assert abs(r0_acc_live[0]) > 1e-6


def test_corpse_still_emits_personal_space_repulsion():
    """Under full observability a corpse is visible, so it is still avoided."""
    assets = [
        Asset(id="b0", class_name="rock", team="blue", x=2.0, y=2.0),
        Asset(id="r0", class_name="scissors", team="red", x=3.0, y=3.0),
    ]
    dyn = Dynamics(assets)
    assets[0].active = 0          # b0 is a corpse
    assets[1].active = 1
    assets[1].target_id = None
    y = [2, 2, 0, 0, 3, 3, 0, 0]
    params = dyn.pack_params(assets, FieldParams(k_wall=0.0))
    _zero(params, "k_a")
    d = dyn.rhs(0.0, y, params)
    # r0 still accelerates away from the (dead, but visible) b0 at (2,2): toward (+,+)
    assert d[6] > 0 and d[7] > 0
