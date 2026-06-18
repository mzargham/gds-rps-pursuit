/** Arena page: load the recorded match, drive playback, draw the survivors chart. */

import { loadMatch } from './data/loader.js';
import { createArena } from './arena/arena.js';
import { createPlayback } from './arena/playback.js';

const PALETTE = {
  ink: '#2a2520',
  dim: '#8a8278',
  blue: '#4a90d9',
  red: '#e74c3c',
};

function drawSurvivorChart(match) {
  const series = match.survivor_series;
  const t = series.map((s) => s.t);
  const blue = series.map((s) => s.blue || 0);
  const red = series.map((s) => s.red || 0);
  const teamColor = (team, fb) =>
    (match.teams[team] && match.teams[team].color) || fb;

  const traces = [
    {
      x: t, y: blue, name: 'Blue', mode: 'lines',
      line: { color: teamColor('blue', PALETTE.blue), width: 3, shape: 'hv' },
    },
    {
      x: t, y: red, name: 'Red', mode: 'lines',
      line: { color: teamColor('red', PALETTE.red), width: 3, shape: 'hv' },
    },
  ];
  const layout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'rgba(255,253,249,0.6)',
    font: { family: 'IBM Plex Mono, monospace', size: 11, color: PALETTE.dim },
    margin: { l: 40, r: 16, t: 10, b: 36 },
    xaxis: { title: 'time (s)', gridcolor: 'rgba(0,0,0,0.06)', zeroline: false },
    yaxis: { title: 'assets alive', dtick: 1, rangemode: 'tozero',
             gridcolor: 'rgba(0,0,0,0.06)' },
    legend: { orientation: 'h', y: 1.15 },
    shapes: [{
      type: 'line', x0: 0, x1: 0, yref: 'paper', y0: 0, y1: 1,
      line: { color: PALETTE.ink, width: 1, dash: 'dot' },
    }],
  };
  Plotly.newPlot('survChart', traces, layout, { displayModeBar: false, responsive: true });
}

function moveCursor(t) {
  Plotly.relayout('survChart', { 'shapes[0].x0': t, 'shapes[0].x1': t });
}

async function boot() {
  const match = await loadMatch();

  document.getElementById('outcome').textContent =
    match.outcome === 'timeout' || match.outcome === 'draw'
      ? `— ${match.outcome} (${match.duration}s)`
      : `— ${match.outcome} wins (${match.duration}s)`;
  document.getElementById('instanceNote').textContent =
    `${match.name}: ${match.description}`;

  const canvas = document.getElementById('arena');
  const arena = createArena(canvas, match);
  drawSurvivorChart(match);

  const dom = {
    play: document.getElementById('play'),
    stepF: document.getElementById('stepF'),
    stepB: document.getElementById('stepB'),
    reset: document.getElementById('reset'),
    scrub: document.getElementById('scrub'),
    speed: document.getElementById('speed'),
    tReadout: document.getElementById('tReadout'),
    blueScore: document.getElementById('blueScore'),
    redScore: document.getElementById('redScore'),
  };
  createPlayback(arena, match, dom, moveCursor);
}

boot().catch((err) => {
  document.querySelector('.wrap').insertAdjacentHTML(
    'beforeend',
    `<p class="disclaimer">Failed to load match data: ${err.message}.
     Run <code>uv run python generate.py</code> in <code>pipeline/</code> first.</p>`,
  );
  console.error(err);
});
