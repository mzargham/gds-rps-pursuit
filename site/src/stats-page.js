/** Analysis page: aggregate stats over repeated runs — the model-driven tuning story. */

import { loadStats } from './data/loader.js';

const C = { blue: '#4a90d9', red: '#e74c3c', dim: '#8a8278', accent: '#6a5acd',
            gold: '#d4a017', cyan: '#3a9fd0', purple: '#a86ed2' };

const BASE = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'rgba(255,253,249,0.6)',
  font: { family: 'IBM Plex Mono, monospace', size: 11, color: C.dim },
  margin: { l: 48, r: 16, t: 10, b: 48 },
};
const OPTS = { displayModeBar: false, responsive: true };

function stalemate(o) {
  return (o.draw || 0) + (o.timeout || 0);
}

function renderTakeaway(s) {
  const tk = s.tuning_takeaway;
  document.getElementById('intro').textContent = s.intro;
  document.getElementById('takeaway').innerHTML =
    `<div style="display:flex;gap:2rem;flex-wrap:wrap;align-items:baseline;margin-bottom:0.6rem">
       <div><span style="font-size:1.8rem;font-weight:700;color:${C.red}">${tk.naive_self_elim_pct}%</span>
            <div class="legend">attackers self-eliminated (naive)</div></div>
       <div style="font-size:1.4rem;color:${C.dim}">→</div>
       <div><span style="font-size:1.8rem;font-weight:700;color:${C.blue}">${tk.tuned_self_elim_pct}%</span>
            <div class="legend">after tuning</div></div>
       <div><span style="font-size:1.8rem;font-weight:700;color:${C.accent}">${tk.tuned_decisive_pct}%</span>
            <div class="legend">matches still decisive</div></div>
     </div>
     <p>${tk.text}</p>`;
}

function renderSweep(s) {
  const grid = s.tuning_sweep.grid;
  const labels = grid.map((r) => `eng ${r.engage_factor}\n× ${r.kill_mult} reach`);
  document.getElementById('sweepNote').textContent =
    `Each cell is ${s.tuning_sweep.n} randomized runs. We vary the stand-off distance ` +
    `(engage factor: 0 = charge to contact) and the kill-cone reach (× baseline). ` +
    `Lower self-elimination is better, but only if matches stay decisive.`;
  const traces = [
    { x: labels, y: grid.map((r) => r.self_elim_pct), name: 'self-elimination %',
      type: 'bar', marker: { color: C.red } },
    { x: labels, y: grid.map((r) => r.draw_pct), name: 'stalemate %',
      type: 'bar', marker: { color: C.dim } },
    { x: labels, y: grid.map((r) => r.decisive_pct), name: 'decisive %',
      type: 'bar', marker: { color: C.blue } },
  ];
  Plotly.newPlot('sweepChart',
    traces,
    { ...BASE, height: 300, barmode: 'group',
      legend: { orientation: 'h', y: 1.18 },
      yaxis: { title: '%', range: [0, 100], gridcolor: 'rgba(0,0,0,0.06)' },
      xaxis: { tickangle: 0 } },
    OPTS);

  const rows = grid.map((r) =>
    `<tr><td>${r.engage_factor}</td><td>${r.kill_mult}×</td>
       <td>${r.self_elim_pct}%</td><td>${r.decisive_pct}%</td><td>${r.draw_pct}%</td></tr>`).join('');
  document.getElementById('sweepTable').innerHTML =
    `<table class="tbl"><thead><tr><th>engage factor</th><th>kill reach</th>
       <th>self-elim</th><th>decisive</th><th>stalemate</th></tr></thead>
       <tbody>${rows}</tbody></table>`;
}

function renderOutcomes(s) {
  const o = s.headline.outcomes;
  document.getElementById('outcomeNote').textContent =
    `${s.headline.n} runs, greedy Blue vs random Red, jittered start positions. ` +
    `Mean duration ${s.headline.mean_duration}s, mean spatial spread ${s.headline.mean_spread}.`;
  Plotly.newPlot('outcomeChart',
    [{ type: 'bar',
       x: ['Blue wins', 'Red wins', 'stalemate'],
       y: [o.blue || 0, o.red || 0, stalemate(o)],
       marker: { color: [C.blue, C.red, C.dim] } }],
    { ...BASE, height: 240, yaxis: { title: 'matches', gridcolor: 'rgba(0,0,0,0.06)' } },
    OPTS);
}

function renderDurations(s) {
  Plotly.newPlot('durationChart',
    [{ type: 'histogram', x: s.headline.durations, marker: { color: C.accent },
       xbins: { start: 0, size: 2.5 } }],
    { ...BASE, height: 240,
      xaxis: { title: 'match duration (s)', gridcolor: 'rgba(0,0,0,0.06)' },
      yaxis: { title: 'matches', gridcolor: 'rgba(0,0,0,0.06)' } },
    OPTS);
}

function renderEvents(s) {
  const e = s.headline.event_mix;
  const labels = { rps: 'kill-cone', collision: 'collision', hazard: 'hazard' };
  const keys = ['rps', 'collision', 'hazard'];
  Plotly.newPlot('eventChart',
    [{ type: 'bar', x: keys.map((k) => labels[k]), y: keys.map((k) => e[k] || 0),
       marker: { color: [C.gold, C.cyan, C.purple] } }],
    { ...BASE, height: 240, yaxis: { title: 'avg per match', gridcolor: 'rgba(0,0,0,0.06)' } },
    OPTS);
}

function renderLeaders(s) {
  const m = s.leaders.matchups;
  document.getElementById('leaderNote').textContent =
    `${s.leaders.n} runs per matchup (Blue leader vs Red leader). The greedy ` +
    `policy is a thin heuristic, yet it measurably outperforms random assignment.`;
  const labels = m.map((x) => `${x.blue} vs ${x.red}`);
  Plotly.newPlot('leaderChart',
    [
      { x: labels, y: m.map((x) => x.blue_win_pct), name: 'Blue wins', type: 'bar',
        marker: { color: C.blue } },
      { x: labels, y: m.map((x) => x.red_win_pct), name: 'Red wins', type: 'bar',
        marker: { color: C.red } },
      { x: labels, y: m.map((x) => x.stalemate_pct), name: 'stalemate', type: 'bar',
        marker: { color: C.dim } },
    ],
    { ...BASE, height: 260, barmode: 'group', legend: { orientation: 'h', y: 1.18 },
      yaxis: { title: '%', range: [0, 100], gridcolor: 'rgba(0,0,0,0.06)' } },
    OPTS);
}

async function boot() {
  const s = await loadStats();
  renderTakeaway(s);
  renderSweep(s);
  renderOutcomes(s);
  renderDurations(s);
  renderEvents(s);
  renderLeaders(s);
}

boot().catch((err) => {
  document.querySelector('.wrap').insertAdjacentHTML(
    'beforeend',
    `<p class="disclaimer">Failed to load analysis data: ${err.message}.
     Run <code>uv run python generate.py</code> in <code>pipeline/</code> first.</p>`);
  console.error(err);
});
