/** Data loader — fetches pre-computed JSON from public/data/. */

const cache = new Map();

export async function loadJSON(filename) {
  if (cache.has(filename)) return cache.get(filename);
  const resp = await fetch(`./data/${filename}`);
  if (!resp.ok) throw new Error(`Failed to load ${filename}: ${resp.status}`);
  const data = await resp.json();
  cache.set(filename, data);
  return data;
}

export const loadMatch = () => loadJSON('match.json');
export const loadFormal = () => loadJSON('formal.json');
export const loadVizDiagrams = () => loadJSON('viz_diagrams.json');
export const loadStats = () => loadJSON('stats.json');
