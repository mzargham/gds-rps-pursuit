"""Declarative GDS view: the four block roles, canonical h = f∘g, and the
symbolic expressions the simulation is lambdified from.

This is the *same* system as ``gen_sim``/``dynamics`` seen formally. The motion
mechanism's behaviour is literally the symbolic field in ``dynamics.py`` — we
export that field here so the formal page shows the source the integrator runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import gds
from gds import (
    BoundaryAction,
    ControlAction,
    FlowDirection,
    GDSSpec,
    Mechanism,
    Policy,
    Wiring,
    compile_system,
    entity,
    interface,
    project_canonical,
    state_var,
    typedef,
    verify,
)

from dynamics import GLOBAL_GAINS, PER_ASSET_GAINS, Dynamics
from gen_sim import load_instance
from ontology import ontology_summary

# Schematic parameter names for the (type-level) GDS spec. The executable field
# expands the per-asset gains to k_a_i, k_r_i, … one per asset (see dynamics.py).
SPEC_PARAMS = PER_ASSET_GAINS + ["eps", "F_wall", "k_wall"]

# ---------------------------------------------------------------------------
# Types & entities (the state space X — schematic; one entity per team)
# ---------------------------------------------------------------------------
Pose = typedef("Pose", float, description="Asset configuration (position) in the arena")
Velocity = typedef("Velocity", float, description="Asset velocity")
Active = typedef("Active", int, constraint=lambda v: v in (0, 1),
                 description="Admissible-action gate: 1 active, 0 destroyed (action space ∅)")
Gain = typedef("Gain", float, description="A field parameter (constant within a match)")

blue_team = entity(
    "BlueTeam",
    position=state_var(Pose, symbol="r^B"),
    velocity=state_var(Velocity, symbol="v^B"),
    active=state_var(Active, symbol="a^B"),
)
red_team = entity(
    "RedTeam",
    position=state_var(Pose, symbol="r^R"),
    velocity=state_var(Velocity, symbol="v^R"),
    active=state_var(Active, symbol="a^R"),
)

# ---------------------------------------------------------------------------
# Blocks (the four GDS roles)
# ---------------------------------------------------------------------------
spawn = BoundaryAction(
    name="Spawn",
    interface=interface(forward_out=["World State"]),
)
blue_leader = Policy(
    name="Blue Leader",
    interface=interface(forward_in=["World State"], forward_out=["Blue Task Weights"]),
)
red_leader = Policy(
    name="Red Leader",
    interface=interface(forward_in=["World State"], forward_out=["Red Task Weights"]),
)
motion = Mechanism(
    name="Motion",
    interface=interface(
        forward_in=["Blue Task Weights", "Red Task Weights"],
        forward_out=["Updated Poses"],
    ),
    updates=[
        ("BlueTeam", "position"), ("BlueTeam", "velocity"),
        ("RedTeam", "position"), ("RedTeam", "velocity"),
    ],
    params_used=SPEC_PARAMS,
)
engagement = Mechanism(
    name="Engagement",
    interface=interface(forward_in=["Updated Poses"], forward_out=["World State"]),
    updates=[("BlueTeam", "active"), ("RedTeam", "active")],
)
observe = ControlAction(
    name="Observe",
    interface=interface(forward_in=["Updated Poses"], forward_out=["Survivor Counts"]),
)


def build_system():
    """Compose the roles into the GDS system (with the temporal loop)."""
    core = spawn >> (blue_leader | red_leader) >> motion >> (engagement | observe)
    loop = core.loop([
        Wiring(source_block="Engagement", source_port="World State",
               target_block="Blue Leader", target_port="World State",
               direction=FlowDirection.COVARIANT),
        Wiring(source_block="Engagement", source_port="World State",
               target_block="Red Leader", target_port="World State",
               direction=FlowDirection.COVARIANT),
    ])
    return compile_system("rps_pursuit", loop)


def build_spec() -> GDSSpec:
    spec = GDSSpec(
        name="RPS Pursuit",
        description="Two-team rock-paper-scissors pursuit-evasion as a GDS.",
    )
    spec.collect(
        Pose, Velocity, Active, Gain,
        blue_team, red_team,
        spawn, blue_leader, red_leader, motion, engagement, observe,
    )
    for g in SPEC_PARAMS:
        spec.register_parameter(g, Gain)
    return spec


def generate_formal(instance_path: Path) -> dict:
    spec = build_spec()
    system = build_system()
    report = verify(system)
    canonical = project_canonical(spec)

    # the symbolic field the sim is lambdified from (representative asset 0)
    inst = load_instance(instance_path)
    dyn = Dynamics(inst["assets"])
    sym = {
        "n_assets": dyn.N,
        "potential_latex": dyn.potential_latex(0),
        "accel_latex": dyn.rhs_latex(0),
        "param_names": PER_ASSET_GAINS + GLOBAL_GAINS,
        "note": (
            "The Motion mechanism f is this symbolic potential field. It is "
            "lambdified exactly once; discrete engagements only flip the "
            "parameters active_i (admissible-action gate) and w_ij (task weight). "
            "The gains k_a, k_r, c, F_chase, F_flee are per-asset, read from each "
            "asset's class — so the three RPS types move differently."
        ),
    }

    blocks = [
        {"name": b.name, "role": type(b).__name__,
         "forward_in": [p.name for p in b.interface.forward_in],
         "forward_out": [p.name for p in b.interface.forward_out],
         "updates": [list(u) for u in getattr(b, "updates", [])]}
        for b in (spawn, blue_leader, red_leader, motion, engagement, observe)
    ]

    return {
        "title": "Formal Structure",
        "description": (
            "The same pursuit-evasion system viewed as a Generalized Dynamical "
            "System: h = f∘g, with leaders as the policy g and Motion+Engagement "
            "as the mechanism f."
        ),
        "verification": {
            "errors": report.errors,
            "warnings": report.warnings,
            "checks_passed": report.checks_passed,
            "checks_total": report.checks_total,
        },
        "blocks": blocks,
        "canonical": {
            "policy_blocks": list(canonical.policy_blocks),
            "mechanism_blocks": list(canonical.mechanism_blocks),
            "boundary_blocks": list(canonical.boundary_blocks),
            "control_blocks": list(canonical.control_blocks),
            "state_variables": [list(s) for s in canonical.state_variables],
            "update_map": [[m, [list(t) for t in reads]] for m, reads in canonical.update_map],
        },
        "symbolic": sym,
        "ontology": ontology_summary(),
    }


if __name__ == "__main__":
    here = Path(__file__).parent
    data = generate_formal(here / "instances" / "skirmish_3v3.json")
    v = data["verification"]
    print(f"verify: errors={v['errors']} passed={v['checks_passed']}/{v['checks_total']}")
    print("policy g:", data["canonical"]["policy_blocks"])
    print("mechanism f:", data["canonical"]["mechanism_blocks"])
