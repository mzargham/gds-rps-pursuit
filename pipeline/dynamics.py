"""The symbolic vector field — the single source of truth bound to the sim.

The entire game's continuous motion is ONE potential-based vector field over all
assets, built symbolically with SymPy and turned into a numeric right-hand side by
``sympy.lambdify`` **exactly once** (mirrors
``gds-examples/continuous/homicidal_chauffeur/model.py``). Discrete events never
re-derive or re-lambdify the field — they only flip its *parameters*:

- ``active_i`` ∈ {0,1} — the admissible-action gate. 1 while asset ``i`` can act;
  0 once destroyed (its admissible action space has collapsed to ∅). It gates both
  ``i``'s own control and ``i``'s influence on others.
- ``w_ij``  ∈ [0,1] — the leader-assigned task weight (how strongly ``i`` pursues
  ``j``). Naive leaders set this to a 0/1 indicator of ``i``'s assigned target.

Each asset's gains (``k_a_i``, ``k_r_i``, ``c_i``, ``F_chase_i``, ``F_flee_i``) are
*per-asset* parameters, read from that asset's ``AssetClass``. The three RPS classes
have different kinematics, so the types move differently. Per asset ``i``
(positions ``r_i = (x_i, y_i)``, velocity ``v_i``):

    U^att_i = ½·k_a_i · Σ_j w_ij·active_j·(d_ij − r0_i)²   (pursue to stand-off r0_i)
    U^rep_i = Σ_j [ k_r_i·P_ij·active_j + k_space·(1−w_ij) ]·(1/d_ij)
                                                       (flee live predators + keep personal space)
    U^wall_i = k_wall · wall(r_i)                      (stay in the arena)

The predator-flee term is gated by ``active_j`` (a destroyed predator no longer
threatens), but the personal-space term is NOT: under full observability a corpse is
still visible, so it is still avoided. Corpses therefore repel (steer-around
behaviour) yet remain lethal on contact (the hazard rule in ``engagement.py``).
    a_i = active_i · [ F_chase_i·tanh(−∇U^att_i / F_chase_i)
                     + F_flee_i ·tanh(−∇U^rep_i / F_flee_i)
                     + F_wall  ·tanh(−∇U^wall_i / F_wall) ]
    dr_i/dt  = v_i
    dv_i/dt  = a_i − c_i · v_i                         (second-order, damped)

with softened distance ``d_ij = sqrt(|r_i − r_j|² + eps)`` and static enemy-predator
indicator ``P_ij = 1`` iff team(j) ≠ team(i) and type(j) beats type(i).

The pursuit and evasion drives saturate *independently*: with F_chase > F_flee a
chaser is more agile than its target, so pursuits terminate (without that split a
single tanh cap would equalise pursuer and evader — the classic homicidal-chauffeur
non-capture).

``Dynamics.reference_rhs`` re-implements the field by hand in NumPy; the test suite
asserts it equals the lambdified field on random inputs — the proof that the
simulation reflects the formalism.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import sympy as sp

from ontology import Asset, beats

# Per-asset gains (read from each asset's AssetClass) and the class attribute each maps to.
PER_ASSET_GAINS = ["k_a", "k_r", "c", "F_chase", "F_flee", "r0"]
_GAIN_TO_ATTR = {
    "k_a": "attract_gain", "k_r": "repel_gain", "c": "damping",
    "F_chase": "chase", "F_flee": "flee", "r0": "engage_radius",
}
# Global field parameters (constant within a match, shared by all assets).
GLOBAL_GAINS = ["eps", "F_wall", "k_wall", "wall_w", "k_space", "W", "H"]


@dataclass(frozen=True)
class FieldParams:
    """Global field parameters (per-asset gains come from each asset's class)."""

    eps: float = 0.05      # distance softening (avoids the 1/d singularity)
    F_wall: float = 2.0    # wall-avoidance control saturation
    k_wall: float = 1.5    # arena wall strength
    wall_w: float = 0.8    # arena wall width
    k_space: float = 0.7   # personal-space / collision-avoidance repulsion
    W: float = 16.0        # arena width
    H: float = 16.0        # arena height

    def as_dict(self) -> dict[str, float]:
        return {g: getattr(self, g) for g in GLOBAL_GAINS}


def _wall(coord: sp.Symbol, lo, hi, width, k_wall):
    """Smooth inward push near the [0, hi] boundaries (exponential walls)."""
    return k_wall * (sp.exp(-(coord - lo) / width) + sp.exp((coord - hi) / width))


class Dynamics:
    """Builds the symbolic field for a fixed roster of assets and lambdifies once."""

    def __init__(self, assets: list[Asset]) -> None:
        self.assets = list(assets)
        self.N = len(self.assets)
        self.ids = [a.id for a in self.assets]

        # ---- symbols -----------------------------------------------------
        x = [sp.Symbol(f"x_{i}", real=True) for i in range(self.N)]
        y = [sp.Symbol(f"y_{i}", real=True) for i in range(self.N)]
        vx = [sp.Symbol(f"vx_{i}", real=True) for i in range(self.N)]
        vy = [sp.Symbol(f"vy_{i}", real=True) for i in range(self.N)]
        active = [sp.Symbol(f"active_{i}", real=True) for i in range(self.N)]

        # per-asset gain symbols: g[name][i]
        g = {name: [sp.Symbol(f"{name}_{i}", real=True) for i in range(self.N)]
             for name in PER_ASSET_GAINS}
        ka, kr, cc, fch, ffl, r0 = (
            g["k_a"], g["k_r"], g["c"], g["F_chase"], g["F_flee"], g["r0"]
        )

        # ordered enemy/target pairs (i, j), i != j → one weight symbol each
        self.pairs: list[tuple[int, int]] = [
            (i, j) for i in range(self.N) for j in range(self.N) if i != j
        ]
        w = {(i, j): sp.Symbol(f"w_{i}_{j}", real=True) for (i, j) in self.pairs}

        eps, F_wall, k_wall, wall_w, k_space, W, H = sp.symbols(
            "eps F_wall k_wall wall_w k_space W H", real=True
        )

        # static enemy-predator indicator P_ij (team & type are fixed)
        def pred(i: int, j: int) -> int:
            ai, aj = self.assets[i], self.assets[j]
            return int(ai.team != aj.team and beats(aj.type, ai.type))

        # ---- per-asset split potential, gated saturated control, RHS -----
        rhs_exprs: list[sp.Expr] = []
        self._U: list[sp.Expr] = []  # total potential (for the formal view)
        for i in range(self.N):
            U_att = sp.Integer(0)
            U_rep = sp.Integer(0)
            for j in range(self.N):
                if i == j:
                    continue
                d_ij = sp.sqrt((x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2 + eps)
                # spring to stand-off distance r0_i (min at d=r0_i): approach then hold
                U_att += ka[i] * w[(i, j)] * active[j] * (d_ij - r0[i]) ** 2 / 2
                # repulsion = personal space (every visible body, alive OR corpse,
                # except i's assigned target) + predator-flee (live enemies that beat i)
                rep_term = k_space * (1 - w[(i, j)])
                if pred(i, j):
                    rep_term = rep_term + kr[i] * active[j]
                U_rep += rep_term * (1 / d_ij)
            U_wall = _wall(x[i], 0, W, wall_w, k_wall) + _wall(y[i], 0, H, wall_w, k_wall)
            self._U.append(U_att + U_rep + U_wall)

            def control(U, F, coord):
                grad = -sp.diff(U, coord)
                return F * sp.tanh(grad / F)

            ax = active[i] * (control(U_att, fch[i], x[i])
                              + control(U_rep, ffl[i], x[i])
                              + control(U_wall, F_wall, x[i]))
            ay = active[i] * (control(U_att, fch[i], y[i])
                              + control(U_rep, ffl[i], y[i])
                              + control(U_wall, F_wall, y[i]))

            # state order per asset: x, y, vx, vy
            rhs_exprs.extend([vx[i], vy[i], ax - cc[i] * vx[i], ay - cc[i] * vy[i]])

        self.state_names = [
            name for i in range(self.N) for name in (f"x_{i}", f"y_{i}", f"vx_{i}", f"vy_{i}")
        ]

        ordered_state_syms = [
            s for i in range(self.N) for s in (x[i], y[i], vx[i], vy[i])
        ]
        ordered_param_syms = (
            active
            + [w[(i, j)] for (i, j) in self.pairs]
            + [g[name][i] for name in PER_ASSET_GAINS for i in range(self.N)]
            + [eps, F_wall, k_wall, wall_w, k_space, W, H]
        )

        # ★ THE single lambdify — the spec→sim binding happens here, once.
        self._fn = sp.lambdify(
            ordered_state_syms + ordered_param_syms, rhs_exprs, modules="numpy"
        )
        self._pred = {(i, j): pred(i, j) for (i, j) in self.pairs}

    # ------------------------------------------------------------------
    # Parameter packing (the only thing discrete events change)
    # ------------------------------------------------------------------
    def pack_params(self, assets: list[Asset], field: FieldParams) -> dict[str, float]:
        """Build the parameter dict from the current roster, classes, and globals.

        ``w_ij`` is a 0/1 indicator of ``i``'s assigned target (naive policy); a
        richer policy could set fractional / multiple weights here instead. Per-asset
        gains are read from each asset's ``AssetClass``.
        """
        idx = {a.id: i for i, a in enumerate(assets)}
        params: dict[str, float] = {}
        for i, a in enumerate(assets):
            params[f"active_{i}"] = float(a.active)
            cls = a.asset_class
            for name in PER_ASSET_GAINS:
                params[f"{name}_{i}"] = float(getattr(cls, _GAIN_TO_ATTR[name]))
        for (i, j) in self.pairs:
            tgt = assets[i].target_id
            params[f"w_{i}_{j}"] = 1.0 if (tgt is not None and idx.get(tgt) == j) else 0.0
        params.update(field.as_dict())
        return params

    def _arg_vector(self, y: list[float], params: dict[str, float]) -> list[float]:
        args = list(y)
        args += [params[f"active_{i}"] for i in range(self.N)]
        args += [params[f"w_{i}_{j}"] for (i, j) in self.pairs]
        args += [params[f"{name}_{i}"] for name in PER_ASSET_GAINS for i in range(self.N)]
        args += [params[name] for name in GLOBAL_GAINS]
        return args

    def rhs(self, t: float, y: list[float], params: dict[str, float]) -> list[float]:
        """Lambdified field — the RHS handed to gds_continuous (t, y, params)."""
        result = self._fn(*self._arg_vector(y, params))
        return [float(v) for v in result]

    # ------------------------------------------------------------------
    # Hand-coded twin (NumPy) — used only to prove the binding in tests
    # ------------------------------------------------------------------
    def reference_rhs(self, t: float, y: list[float], params: dict[str, float]) -> list[float]:
        """Independent re-implementation of the same field, for the binding test."""
        N = self.N
        px = [y[4 * i + 0] for i in range(N)]
        py = [y[4 * i + 1] for i in range(N)]
        pvx = [y[4 * i + 2] for i in range(N)]
        pvy = [y[4 * i + 3] for i in range(N)]
        eps = params["eps"]; F_wall = params["F_wall"]; k_wall = params["k_wall"]
        wall_w = params["wall_w"]; k_space = params["k_space"]
        W = params["W"]; H = params["H"]
        act = [params[f"active_{i}"] for i in range(N)]

        def sat(grad, F):
            return F * math.tanh(grad / F)

        out: list[float] = []
        for i in range(N):
            ka = params[f"k_a_{i}"]; kr = params[f"k_r_{i}"]; cc = params[f"c_{i}"]
            fch = params[f"F_chase_{i}"]; ffl = params[f"F_flee_{i}"]; r0 = params[f"r0_{i}"]
            gax = gay = 0.0   # attraction gradient (pursuit)
            grx = gry = 0.0   # repulsion gradient (evasion)
            for j in range(N):
                if i == j:
                    continue
                dx = px[i] - px[j]; dy = py[i] - py[j]
                d = math.sqrt(dx * dx + dy * dy + eps)
                w_ij = params[f"w_{i}_{j}"]
                # attraction (spring to r0): -d/dr_i [ k_a w act_j (d-r0)^2/2 ]
                #                            = -k_a w act_j (d-r0) (r_i - r_j)/d
                ga = -ka * w_ij * act[j] * (d - r0) / d
                gax += ga * dx; gay += ga * dy
                # repulsion: personal space (ungated, visible body) + predator-flee
                # (gated by act[j]); -d/dr_i [ rep / d ] = +rep (r_i - r_j)/d^3
                rep = k_space * (1 - w_ij) + (kr * act[j] if self._pred[(i, j)] else 0.0)
                gr = rep / (d ** 3)
                grx += gr * dx; gry += gr * dy
            # walls: -d/dx [ k_wall (exp(-x/wall_w)+exp((x-W)/wall_w)) ]
            gwx = k_wall / wall_w * (math.exp(-px[i] / wall_w) - math.exp((px[i] - W) / wall_w))
            gwy = k_wall / wall_w * (math.exp(-py[i] / wall_w) - math.exp((py[i] - H) / wall_w))
            axc = act[i] * (sat(gax, fch) + sat(grx, ffl) + sat(gwx, F_wall))
            ayc = act[i] * (sat(gay, fch) + sat(gry, ffl) + sat(gwy, F_wall))
            out.extend([pvx[i], pvy[i], axc - cc * pvx[i], ayc - cc * pvy[i]])
        return out

    # ------------------------------------------------------------------
    # Formal export
    # ------------------------------------------------------------------
    def potential_latex(self, i: int = 0) -> str:
        """LaTeX of asset i's potential U_i (for the formal page)."""
        return sp.latex(self._U[i])

    def rhs_latex(self, i: int = 0) -> dict[str, str]:
        """LaTeX of asset i's control gradient components."""
        x_i = sp.Symbol(f"x_{i}", real=True)
        y_i = sp.Symbol(f"y_{i}", real=True)
        return {
            "dvx": sp.latex(-sp.diff(self._U[i], x_i)),
            "dvy": sp.latex(-sp.diff(self._U[i], y_i)),
        }
