/** Playback controller: drives the arena over the recorded trajectory. */

export function createPlayback(arena, match, dom, onTick) {
  const teamOf = Object.fromEntries(match.roster.map((r) => [r.id, r.team]));
  const frames = match.trajectory;
  const frameDt = frames.length > 1 ? frames[1].t - frames[0].t : 0.1;

  let idx = 0;
  let playing = false;
  let speed = 1;
  let acc = 0;
  let last = 0;

  dom.scrub.max = String(frames.length - 1);

  function counts(frame) {
    const c = { blue: 0, red: 0 };
    for (const a of frame.assets) if (a.active === 1) c[teamOf[a.id]]++;
    return c;
  }

  function render() {
    arena.draw(idx);
    const f = frames[idx];
    const c = counts(f);
    dom.tReadout.textContent = `t = ${f.t.toFixed(1)}s`;
    dom.blueScore.textContent = `BLUE ${c.blue}`;
    dom.redScore.textContent = `RED ${c.red}`;
    dom.scrub.value = String(idx);
    if (onTick) onTick(f.t);
  }

  function setIdx(i) {
    idx = Math.max(0, Math.min(frames.length - 1, i));
    render();
  }

  function tick(now) {
    if (!playing) return;
    if (!last) last = now;
    acc += (now - last) / 1000;
    last = now;
    const step = frameDt / speed;
    while (acc >= step) {
      acc -= step;
      if (idx >= frames.length - 1) {
        playing = false;
        dom.play.textContent = '▶ play';
        break;
      }
      idx++;
    }
    render();
    if (playing) requestAnimationFrame(tick);
  }

  function play() {
    if (idx >= frames.length - 1) idx = 0;
    playing = true;
    last = 0;
    acc = 0;
    dom.play.textContent = '⏸ pause';
    requestAnimationFrame(tick);
  }
  function pause() {
    playing = false;
    dom.play.textContent = '▶ play';
  }

  dom.play.onclick = () => (playing ? pause() : play());
  dom.stepF.onclick = () => { pause(); setIdx(idx + 1); };
  dom.stepB.onclick = () => { pause(); setIdx(idx - 1); };
  dom.reset.onclick = () => { pause(); setIdx(0); };
  dom.scrub.oninput = (e) => { pause(); setIdx(Number(e.target.value)); };
  dom.speed.onchange = (e) => { speed = Number(e.target.value); };

  render();
  return { play, pause, setIdx };
}
