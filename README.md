# gds-rps-pursuit

A **toy world for exploring two-team adversarial dynamic games**, built on the
[Generalized Dynamical Systems](https://doi.org/10.57938/e8d456ea-d975-4111-ac41-052ce73cb0cc)
formalism ([`gds-core`](../gds-core)). Two teams of rock/paper/scissors assets pursue
and evade one another in a shared 2D arena; team leaders assign tasks; assets move
under a single energy field; contact is resolved by rock-paper-scissors.

> **This is a demonstration, not a product.** Its purpose is to show a *methodology* —
> how a GDS specification can be **bound to its simulation through SymPy** so the running
> simulation provably reflects the formalism — illustrated on a deliberately small game.
> It is **not** a solver, a validated pursuit/combat model, or a finished research
> artifact. Read the [Simplifying assumptions](#simplifying-assumptions) before drawing
> any conclusion from it.

## What this is

The whole game is **one symbolic vector field**. Each asset feels an energy potential —
attraction toward its leader-assigned target, repulsion from the enemies that beat it,
and soft arena walls. That potential is differentiated and turned into a numeric
right-hand side by `sympy.lambdify` **exactly once** (the same pattern as
`gds-core`'s `homicidal_chauffeur` example). The continuous flow is integrated by
`gds-continuous` (SciPy `solve_ivp`); rock-paper-scissors captures and leader
reassignments happen between integration segments.

The key idea: discrete events never re-derive the dynamics. A destroyed asset's
**admissible action space collapses to ∅**, modeled as a parameter flip (`active_i = 0`)
on the *same* lambdified field. Because the simulation is compiled from the symbolic
spec, it cannot drift from it — a fact the test suite checks directly
(`tests/test_dynamics.py::test_lambdified_matches_reference`).

The project mirrors the structure of [`gds-axelrod`](../gds-axelrod): a Python
`pipeline/` that emits JSON, and a static `site/` that visualizes it.

- **Arena page** — replays a recorded match: assets as team-colored R/P/S glyphs, a
  survivors-over-time chart, playback controls.
- **Formal page** — the same system as a GDS: the symbolic energy field (rendered with
  KaTeX), the canonical `h = f∘g` decomposition (leaders are the policy `g`;
  Motion + Engagement are the mechanism `f`), `gds-viz` Mermaid diagrams, and the asset
  ontology.
- **Analysis page** — aggregate statistics over hundreds of randomized runs that narrate
  how the model was tuned by *measurement* (e.g. self-elimination rate vs stand-off
  distance and kill-cone reach; leader-policy win rates). This is the payoff of a
  spec-driven model: every design choice is a measurable experiment, not an argument.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/) and Node 18+. Expects `gds-core` checked
out as a sibling directory (`../gds-core`).

```bash
# 1. generate the data
cd pipeline
uv sync
uv run python generate.py          # writes output/*.json and copies into ../site/public/data
uv run pytest                      # optional: run the test suite

# 2. view it
cd ../site
npm install
npm run dev                        # open http://localhost:5173
```

Edit a scenario in `pipeline/instances/`, re-run `generate.py`, refresh the browser.

## Repository layout

```
pipeline/
  ontology.py      asset taxonomy: types (RPS beats-cycle), classes, instances
  dynamics.py      ★ the single symbolic vector field, lambdified once (spec↔sim binding)
  leaders.py       the policy g: task assignment (greedy / fixed / random; built for richer policies)
  engagement.py    kill cone + collision + corpse hazard → admissible-action collapse
  match.py         the hybrid loop: gds_continuous segments × reassignment × engagement
  gen_sim.py       run an instance → match.json
  gen_formal.py    GDSSpec + canonical h=f∘g + symbolic export → formal.json
  gen_viz.py       gds-viz Mermaid diagrams → viz_diagrams.json
  gen_stats.py     repeated-run analysis (tuning sweeps, outcomes) → stats.json
  generate.py      orchestrator
  instances/       scenario configs
  tests/           binding-integrity, engagement, and match-sanity tests
site/              Vite static site (arena replay · formal structure · analysis)
```

## Simplifying assumptions

This is a toy. In v1:

- Assets are **second-order point masses** in a bounded 2D arena; no real-world geometry.
- Policies are **naive heuristics only** — greedy / fixed / random target assignment.
  There is **no optimization, learning, or equilibrium solving**. (The leader interface
  is built to support richer state-dependent / cooperative policies later; none ship yet.)
- The motion field is a **hand-tuned toy potential** (stand-off attraction to a target
  engagement distance + predator repulsion + personal-space repulsion + soft walls) with
  hand-picked gains; pursuit saturates more agilely than evasion so that pursuits
  terminate, and attackers engage from cone reach rather than ramming — explicit modeling
  choices, not derived properties.
- **Full observability**: every asset and corpse is visible to all. The personal-space
  repulsion is treated as a consequence of that visibility, so corpses are avoided
  (steered around) as well as dangerous on contact.
- Resolution is **fixed-cadence**: engagements and reassignments occur at sampling
  boundaries, not at the exact contact instant (no `solve_ivp` event root-finding).
- Destroyed assets are **gated off** as actors (admissible action space → ∅; no control,
  no predator threat) but remain visible in the state — they still emit personal-space
  repulsion and act as collision hazards. Their residual coasting is not analyzed.
- Three interaction rules: **RPS kill cone** (an attacker destroys a prey-type enemy
  inside a wedge — `kill_radius` + half-angle — measured from its heading, so it must be
  facing and moving toward the prey), **collision** (two asset bodies overlapping — drawn
  1:1 as the `collision_radius` circle — both die, any type/team), and **hazard** (a
  corpse destroys a live asset on body overlap). The match is **deterministic** (no noise).
- The shipped instance is tuned to end decisively for a clear demo; other rosters can
  stalemate (e.g. a residual same-type pair), which is a legitimate outcome.

## What this does **not** claim

No optimal or equilibrium strategies. No physical realism. No performance or scaling
claims. The outcome of the shipped match illustrates the *dynamics and the formalism*,
not the tactical superiority of any leader or asset type.

## Where this could go (future work, not promises)

- Richer state-dependent and **cooperative team policies** (the `Leader` interface
  already admits them; weights `w_ij` can be fractional / multi-target).
- **Optimal / learned control** and differential-game analysis — `gds-core` already
  ships homicidal-chauffeur reachability tooling to build on.
- Exact capture-time events via `solve_ivp` event functions.
- Analysis pages (parameter sweeps / sensitivity, à la `gds-axelrod`'s PSUU page).
- More asset types and interaction rules; an OWL/SHACL export of the ontology.

## Notes

- The site loads Plotly, Mermaid, and KaTeX from CDNs (matching `gds-axelrod`). For a
  hardened deployment, pin them with Subresource Integrity hashes or vendor them locally.
- `gds-core` packages are wired as editable path dependencies (`pipeline/pyproject.toml`,
  `[tool.uv.sources]`); adjust the paths if your checkout differs.
