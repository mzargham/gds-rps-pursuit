/** Canvas renderer for a recorded match: assets as team-colored R/P/S glyphs. */

const TEAM_FALLBACK = { blue: '#4a90d9', red: '#e74c3c' };
const HAZARD = '#a86ed2'; // corpse / hazard purple (matches the legend + hazard flash)

export function createArena(canvas, match) {
  const ctx = canvas.getContext('2d');
  const { W, H } = match.arena;
  const rosterById = Object.fromEntries(match.roster.map((r) => [r.id, r]));
  const teamColor = (team) =>
    (match.teams[team] && match.teams[team].color) || TEAM_FALLBACK[team] || '#888';

  // crisp rendering at device pixel ratio
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const cssSize = Math.min(560, canvas.clientWidth || 560);
  canvas.width = cssSize * dpr;
  canvas.height = cssSize * dpr;
  const px = canvas.width;
  const scale = px / Math.max(W, H);
  const sx = (x) => x * scale;
  const sy = (y) => px - y * scale; // y up

  function hexToRgb(hex) {
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
    return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : [136, 136, 136];
  }

  function draw(frameIndex) {
    const frame = match.trajectory[frameIndex];
    const t = frame.t;
    ctx.clearRect(0, 0, px, px);

    // arena border
    ctx.strokeStyle = '#d4cfc6';
    ctx.lineWidth = 2 * dpr;
    ctx.strokeRect(1, 1, px - 2, px - 2);

    // kill cones (drawn first, behind bodies). screen y is flipped, so the
    // screen-space heading angle is atan2(-vy, vx).
    for (const a of frame.assets) {
      if (a.active !== 1) continue;
      const meta = rosterById[a.id];
      const speed = Math.hypot(a.vx || 0, a.vy || 0);
      if (speed < 1e-3 || !meta.kill_radius) continue;
      const heading = Math.atan2(-(a.vy || 0), a.vx || 0);
      const half = meta.kill_half_angle;
      const r = meta.kill_radius * scale;
      const [cr, cg, cb] = hexToRgb(teamColor(meta.team));
      ctx.beginPath();
      ctx.moveTo(sx(a.x), sy(a.y));
      ctx.arc(sx(a.x), sy(a.y), r, heading - half, heading + half);
      ctx.closePath();
      ctx.fillStyle = `rgba(${cr},${cg},${cb},0.13)`;
      ctx.fill();
    }

    // event flashes near current time, colored by kind
    const FLASH = {
      rps: [230, 180, 40],       // gold — type beats type
      collision: [120, 215, 255], // cyan — both destroyed
      hazard: [170, 110, 210],    // purple — corpse hazard
    };
    for (const ev of match.events) {
      const age = t - ev.t;
      if (age >= 0 && age < 1.0) {
        const r = (0.4 + age * 2.2) * scale;
        const [cr, cg, cb] = FLASH[ev.kind] || FLASH.rps;
        ctx.beginPath();
        ctx.arc(sx(ev.x), sy(ev.y), r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${cr},${cg},${cb},${(1 - age) * 0.9})`;
        ctx.lineWidth = 3 * dpr;
        ctx.stroke();
      }
    }

    for (const a of frame.assets) {
      const meta = rosterById[a.id];
      const alive = a.active === 1;
      // body radius = collision_radius (1:1 with the physics: two bodies
      // touching is exactly a collision)
      const rAsset = (meta.collision_radius || 0.4) * scale;
      // a corpse is a team-neutral hazard, drawn in the hazard purple
      ctx.globalAlpha = alive ? 1 : 0.6;

      ctx.beginPath();
      ctx.arc(sx(a.x), sy(a.y), rAsset, 0, Math.PI * 2);
      ctx.fillStyle = alive ? teamColor(meta.team) : HAZARD;
      ctx.fill();
      ctx.lineWidth = 2 * dpr;
      ctx.strokeStyle = alive ? 'rgba(0,0,0,0.35)' : 'rgba(90,40,120,0.7)';
      ctx.stroke();

      // glyph
      ctx.globalAlpha = alive ? 1 : 0.75;
      ctx.fillStyle = '#fff';
      ctx.font = `bold ${Math.round(rAsset * 1.2)}px IBM Plex Mono, monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(meta.glyph, sx(a.x), sy(a.y) + dpr);
    }
    ctx.globalAlpha = 1;
  }

  return { draw, nFrames: match.trajectory.length };
}
