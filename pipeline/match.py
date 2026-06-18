"""The hybrid game loop: continuous symbolic flow + discrete RPS resets.

A match is a hybrid automaton. Within a fixed-cadence segment the assets follow
the single lambdified vector field, integrated by ``gds_continuous`` (scipy
``solve_ivp``). At each segment boundary we apply the discrete reset map:

1. resolve RPS engagements (losers' admissible action space collapses to ∅), then
2. let each team leader reassign tasks from the new world state.

Both are pure parameter flips on the *same* field — never a re-derivation. The
loop records a trajectory (per-frame asset poses) + capture events + a survivor
timeline for the presentation layer.
"""

from __future__ import annotations

from gds_continuous import ODEModel, ODESimulation

from dynamics import Dynamics, FieldParams
from engagement import resolve_engagements, survivors
from leaders import Leader
from ontology import Asset


def _frame(assets: list[Asset], t: float) -> dict:
    return {
        "t": round(t, 4),
        "assets": [
            {"id": a.id, "x": round(a.x, 4), "y": round(a.y, 4),
             "vx": round(a.vx, 4), "vy": round(a.vy, 4), "active": a.active}
            for a in assets
        ],
    }


def _apply_assignments(assets: list[Asset], leaders: dict[str, Leader]) -> None:
    by_id = {a.id: a for a in assets}
    for team, leader in leaders.items():
        for aid, tgt in leader.assign(assets, team).items():
            by_id[aid].target_id = tgt


def run_match(
    assets: list[Asset],
    leaders: dict[str, Leader],
    *,
    field: FieldParams | None = None,
    cadence: float = 0.4,
    sample_dt: float = 0.05,
    t_max: float = 40.0,
) -> dict:
    """Run one match and return a serializable result dict."""
    field = field or FieldParams()
    dyn = Dynamics(assets)
    state_names = dyn.state_names

    _apply_assignments(assets, leaders)

    trajectory: list[dict] = [_frame(assets, 0.0)]
    events: list[dict] = []
    survivor_series: list[dict] = [{"t": 0.0, **survivors(assets)}]

    t = 0.0
    outcome = "timeout"
    n_samples = max(1, round(cadence / sample_dt))

    while t < t_max - 1e-9:
        t_end = min(t + cadence, t_max)
        params = dyn.pack_params(assets, field)
        model = ODEModel(
            state_names=state_names,
            initial_state={name: float(v) for name, v in zip(
                state_names,
                [c for a in assets for c in (a.x, a.y, a.vx, a.vy)],
                strict=True,
            )},
            rhs=dyn.rhs,
            params={k: [v] for k, v in params.items()},
        )
        # sample the open-left interval (t, t_end]; the start frame is already recorded
        t_eval = [t + (k + 1) * (t_end - t) / n_samples for k in range(n_samples)]
        results = ODESimulation(model=model, t_span=(t, t_end), t_eval=t_eval).run()

        cols = {name: results.state_array(name) for name in state_names}
        for k in range(len(t_eval)):
            for i, a in enumerate(assets):
                a.x = cols[f"x_{i}"][k]
                a.y = cols[f"y_{i}"][k]
                a.vx = cols[f"vx_{i}"][k]
                a.vy = cols[f"vy_{i}"][k]
            # resolve captures at every sample (finer than the cadence) to avoid
            # fast assets tunnelling past one another between segment boundaries
            seg_events = resolve_engagements(assets, t_eval[k])
            events.extend(seg_events)
            trajectory.append(_frame(assets, t_eval[k]))

        t = t_end

        # ---- leaders reassign tasks from the new world state --------
        _apply_assignments(assets, leaders)
        survivor_series.append({"t": round(t, 4), **survivors(assets)})

        counts = survivors(assets)
        teams = list(leaders.keys())
        alive_teams = [tm for tm in teams if counts.get(tm, 0) > 0]
        if len(alive_teams) <= 1:
            outcome = alive_teams[0] if alive_teams else "draw"
            break

    final = survivors(assets)
    return {
        "outcome": outcome,
        "winner": outcome if outcome in leaders else None,
        "final_survivors": final,
        "duration": round(t, 4),
        "trajectory": trajectory,
        "events": events,
        "survivor_series": survivor_series,
    }
