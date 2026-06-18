/** Formal page: symbolic field (KaTeX), canonical h=f∘g, Mermaid diagrams, ontology. */

import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
import { loadFormal, loadVizDiagrams } from './data/loader.js';

mermaid.initialize({ startOnLoad: false, theme: 'neutral' });

function tex(el, latex, display = true) {
  try {
    window.katex.render(latex, el, { displayMode: display, throwOnError: false });
  } catch (e) {
    el.textContent = latex;
  }
}

function el(tag, props = {}, html) {
  const n = document.createElement(tag);
  Object.assign(n, props);
  if (html !== undefined) n.innerHTML = html;
  return n;
}

function renderVerify(f) {
  const v = f.verification;
  const ok = v.errors === 0;
  document.getElementById('verifyCard').innerHTML =
    `<strong>GDS verification:</strong> ${ok ? '✓ passed' : '✗ failed'} — ` +
    `${v.checks_passed}/${v.checks_total} checks, ${v.errors} errors, ${v.warnings} warnings.`;
}

function renderSymbolic(f) {
  const s = f.symbolic;
  document.getElementById('symNote').textContent = s.note;
  const pot = document.getElementById('potential');
  pot.appendChild(el('div', { className: 'label' },
    `Potential energy of a representative asset (i = 0), over a roster of ${s.n_assets}:`));
  const potMath = el('div');
  pot.appendChild(potMath);
  tex(potMath, `U_0 = ${s.potential_latex}`);

  const acc = document.getElementById('accel');
  acc.appendChild(el('div', { className: 'label' },
    'Its control (negative gradient), before saturation + damping:'));
  const ax = el('div'); acc.appendChild(ax);
  tex(ax, `-\\partial U_0/\\partial x_0 = ${s.accel_latex.dvx}`);
  const ay = el('div'); acc.appendChild(ay);
  tex(ay, `-\\partial U_0/\\partial y_0 = ${s.accel_latex.dvy}`);

  document.getElementById('paramList').textContent =
    'Field parameters (lambdified once; only active_i and w_ij change at events): ' +
    s.param_names.join(', ');
}

function renderCanonical(f) {
  const c = f.canonical;
  document.getElementById('canonical').innerHTML =
    `<div class="card">
       <div><strong>policy g</strong> (decision): ${c.policy_blocks.join(', ')}</div>
       <div><strong>mechanism f</strong> (state update): ${c.mechanism_blocks.join(', ')}</div>
       <div><strong>boundary</strong> (exogenous): ${c.boundary_blocks.join(', ') || '—'}</div>
       <div><strong>observable</strong> (y = C(x)): ${c.control_blocks.join(', ') || '—'}</div>
     </div>`;
}

function renderRoles(f) {
  const rows = f.blocks.map((b) =>
    `<tr><td>${b.name}</td><td>${b.role}</td>
       <td>${b.forward_in.join(', ') || '—'}</td>
       <td>${b.forward_out.join(', ') || '—'}</td>
       <td>${b.updates.map((u) => u.join('.')).join(', ') || '—'}</td></tr>`).join('');
  document.getElementById('rolesTable').innerHTML =
    `<table class="tbl"><thead><tr>
       <th>block</th><th>role</th><th>inputs</th><th>outputs</th><th>updates</th>
     </tr></thead><tbody>${rows}</tbody></table>`;
}

function renderOntology(f) {
  const o = f.ontology;
  const typeRows = o.types.map((t) =>
    `<tr><td>${t.letter} (${t.name})</td><td>beats ${t.beats}</td>
       <td>beaten by ${t.beaten_by}</td></tr>`).join('');
  const classRows = o.classes.map((c) =>
    `<tr><td>${c.name}</td><td>${c.type}</td><td>${c.chase}</td><td>${c.flee}</td>
       <td>${c.collision_radius}</td><td>${c.kill_radius}</td><td>${c.kill_angle_deg}°</td>
       <td>${c.attract_gain}</td><td>${c.repel_gain}</td></tr>`).join('');
  const rules = (o.interaction_rules || []).map((r) => `<li>${r}</li>`).join('');
  document.getElementById('ontology').innerHTML =
    `<div class="card">
       <table class="tbl"><thead><tr><th>type</th><th></th><th></th></tr></thead>
         <tbody>${typeRows}</tbody></table>
       <table class="tbl" style="margin-top:0.8rem"><thead><tr>
         <th>class</th><th>type</th><th>chase</th><th>flee</th>
         <th>collision r</th><th>kill r</th><th>kill ∠</th>
         <th>attract</th><th>repel</th></tr></thead>
         <tbody>${classRows}</tbody></table>
       <ul class="legend" style="margin-top:0.6rem">${rules}</ul>
       <p class="legend">${o.admissibility_note}</p>
     </div>`;
}

async function renderDiagrams(viz) {
  const container = document.getElementById('diagrams');
  let i = 0;
  for (const [key, d] of Object.entries(viz.diagrams)) {
    const wrap = el('div', { className: 'diagram' });
    wrap.appendChild(el('div', { className: 'label' }, d.label));
    const target = el('div');
    wrap.appendChild(target);
    container.appendChild(wrap);
    try {
      const { svg } = await mermaid.render(`m_${key}_${i++}`, d.mermaid);
      target.innerHTML = svg;
    } catch (e) {
      target.innerHTML = `<pre>${d.mermaid}</pre>`;
    }
  }
}

async function boot() {
  const [f, viz] = await Promise.all([loadFormal(), loadVizDiagrams()]);
  renderVerify(f);
  renderSymbolic(f);
  renderCanonical(f);
  renderRoles(f);
  renderOntology(f);
  await renderDiagrams(viz);
}

boot().catch((err) => {
  document.querySelector('.wrap').insertAdjacentHTML(
    'beforeend',
    `<p class="disclaimer">Failed to load formal data: ${err.message}.
     Run <code>uv run python generate.py</code> in <code>pipeline/</code> first.</p>`);
  console.error(err);
});
