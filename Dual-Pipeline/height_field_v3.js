// ============================================================
// TWO-PASS HEIGHT FIELD  v3
//
// Pass 1  surface : screen-space depth pick, top of everything visible
// Pass 2  ground  : bare-earth terrain sampled at those same lon/lat,
//                   including underneath buildings
// Correction      : where pavement is directly visible, the gap between
//                   surface and bare earth is the built-ground offset.
//                   That offset is carried under the buildings.
//
// Requires the viewfinder with Cesium World Terrain loaded.
// Paste into the console, then:
//     await field()
//     await field(48, 27)
// ============================================================

window.field = async function (cols = 32, rows = 18, opts = {}) {
  const scene = viewer.scene;
  if (!scene.pickPositionSupported) { console.error('[Field] depth picking unavailable'); return null; }
  if (!viewer.terrainProvider || !viewer.terrainProvider.tilingScheme) {
    console.error('[Field] No real terrain provider. Reload the viewfinder or run:\n' +
      '  viewer.terrainProvider = await Cesium.createWorldTerrainAsync();');
    return null;
  }

  const w = viewer.canvas.clientWidth;
  const h = viewer.canvas.clientHeight;

  // ---- PASS 1: visible surface ------------------------------
  const cells = [];
  let misses = 0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const px = ((c + 0.5) / cols) * w;
      const py = ((r + 0.5) / rows) * h;
      const cart3 = scene.pickPosition(new Cesium.Cartesian2(px, py));
      if (!Cesium.defined(cart3)) { misses++; continue; }
      const carto = Cesium.Cartographic.fromCartesian(cart3);
      if (!carto || !Number.isFinite(carto.height)) { misses++; continue; }
      cells.push({
        col: c, row: r,
        lon: Cesium.Math.toDegrees(carto.longitude),
        lat: Cesium.Math.toDegrees(carto.latitude),
        surface: carto.height
      });
    }
  }
  if (cells.length < 10) { console.error('[Field] too few surface hits'); return null; }
  console.log(`[Field] Pass 1: ${cells.length} surface hits, ${misses} misses. Sampling terrain...`);

  // ---- PASS 2: bare-earth terrain at the same positions -----
  const probes = cells.map(p => Cesium.Cartographic.fromDegrees(p.lon, p.lat));
  let sampled;
  try {
    sampled = await Cesium.sampleTerrainMostDetailed(viewer.terrainProvider, probes);
  } catch (e) {
    console.error('[Field] terrain sampling failed:', e);
    return null;
  }
  let terrainMisses = 0;
  cells.forEach((p, i) => {
    const t = sampled[i] ? sampled[i].height : undefined;
    if (Number.isFinite(t)) { p.terrain = t; p.raw = p.surface - t; }
    else { terrainMisses++; }
  });
  const good = cells.filter(p => Number.isFinite(p.terrain));
  if (!good.length) { console.error('[Field] no terrain samples returned'); return null; }

  // ---- built-ground offset ----------------------------------
  // Cells whose surface sits closest to bare earth are pavement,
  // garden, or roadway. The median gap for those is how far the
  // built ground sits above the bare-earth model.
  const rawSorted = good.map(p => p.raw).sort((a, b) => a - b);
  const qr = t => rawSorted[Math.min(rawSorted.length - 1, Math.floor(t * rawSorted.length))];
  const groundCut = opts.groundCut ?? qr(0.25);
  const groundCells = good.filter(p => p.raw <= groundCut);
  const offsets = groundCells.map(p => p.raw).sort((a, b) => a - b);
  const offset = opts.offsetOverride ?? offsets[Math.floor(offsets.length / 2)];

  for (const p of good) {
    p.ground = p.terrain + offset;   // corrected built-ground level
    p.agl = p.surface - p.ground;
  }

  // ---- terrain slope across the frame -----------------------
  const lon0 = good.reduce((s, p) => s + p.lon, 0) / good.length;
  const lat0 = good.reduce((s, p) => s + p.lat, 0) / good.length;
  const mLat = 110574, mLon = 111320 * Math.cos(lat0 * Math.PI / 180);
  let See = 0, Snn = 0, Sen = 0, Se = 0, Sn = 0, St = 0, Set_ = 0, Snt = 0;
  for (const p of good) {
    p.e = (p.lon - lon0) * mLon; p.n = (p.lat - lat0) * mLat;
    See += p.e * p.e; Snn += p.n * p.n; Sen += p.e * p.n;
    Se += p.e; Sn += p.n; St += p.ground;
    Set_ += p.e * p.ground; Snt += p.n * p.ground;
  }
  const N = good.length;
  const M = [[See, Sen, Se], [Sen, Snn, Sn], [Se, Sn, N]], V = [Set_, Snt, St];
  const det = m => m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1]) - m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0]) + m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]);
  const D = det(M);
  let plane = { a: 0, b: 0, c: St / N };
  if (Math.abs(D) > 1e-9) {
    const sub = i => { const m = M.map(r => r.slice()); for (let k = 0; k < 3; k++) m[k][i] = V[k]; return det(m) / D; };
    plane = { a: sub(0), b: sub(1), c: sub(2) };
  }
  const slopePct = Math.hypot(plane.a, plane.b) * 100;
  const downhill = (Math.atan2(-plane.a, -plane.b) * 180 / Math.PI + 360) % 360;

  const aglSorted = good.map(p => p.agl).sort((a, b) => a - b);
  const qa = t => aglSorted[Math.min(aglSorted.length - 1, Math.floor(t * aglSorted.length))];
  const camCarto = Cesium.Cartographic.fromCartesian(viewer.camera.position);

  const stats = {
    grid: `${cols} x ${rows}`,
    surfaceHits: cells.length,
    surfaceMisses: misses,
    terrainMisses,
    bareEarthAtCentroid_m: +(plane.c - offset).toFixed(2),
    builtGroundOffset_m: +offset.toFixed(2),
    groundCellsUsed: groundCells.length,
    groundSlope_pct: +slopePct.toFixed(2),
    downhillBearing_deg: +downhill.toFixed(1),
    groundFallAcrossFrame_m: +(Math.max(...good.map(p => p.ground)) - Math.min(...good.map(p => p.ground))).toFixed(2),
    medianAGL_m: +qa(0.5).toFixed(2),
    p90AGL_m: +qa(0.9).toFixed(2),
    maxAGL_m: +qa(1.0).toFixed(2),
    cameraHeight_m: +camCarto.height.toFixed(2),
    heading_deg: +Cesium.Math.toDegrees(viewer.camera.heading).toFixed(1),
    pitch_deg: +Cesium.Math.toDegrees(viewer.camera.pitch).toFixed(1)
  };
  console.log('%c[Field v3] Surface minus corrected ground', 'font-weight:bold');
  console.table(stats);

  // ---- ASCII map --------------------------------------------
  const ramp = '.:-=+*#%@';
  const span = Math.max(1, qa(1.0));
  const grid = Array.from({ length: rows }, () => Array(cols).fill(' '));
  for (const p of good) {
    const t = Math.max(0, Math.min(1, p.agl / span));
    grid[p.row][p.col] = ramp[Math.min(ramp.length - 1, Math.floor(t * ramp.length))];
  }
  console.log('[Field] AGL low to high "' + ramp + '", blank = no hit\n' +
    grid.map(r => r.join('')).join('\n'));

  // ---- skyline + step detection ------------------------------
  const skyline = [];
  for (let c = 0; c < cols; c++) {
    const col = good.filter(p => p.col === c);
    skyline.push(col.length ? +Math.max(...col.map(p => p.agl)).toFixed(1) : null);
  }
  console.log('[Field] Roofline above corrected ground, left to right:');
  console.log(skyline.join('  '));

  const thr = opts.stepThreshold ?? 0.5;
  const med = skyline.map((v, i) => {
    const win = skyline.slice(Math.max(0, i - 1), i + 2).filter(x => x !== null);
    if (!win.length) return null;
    win.sort((a, b) => a - b);
    return win[Math.floor(win.length / 2)];
  });
  const steps = [];
  for (let c = 1; c < cols; c++) {
    if (med[c] === null || med[c - 1] === null) continue;
    const d = med[c] - med[c - 1];
    if (Math.abs(d) >= thr) steps.push({ betweenCols: `${c - 1}|${c}`, delta_m: +d.toFixed(2) });
  }
  console.log('[Field] Roofline steps (threshold ' + thr + ' m):');
  console.table(steps.length ? steps : [{ betweenCols: 'none', delta_m: 0 }]);

  // groundAt(lon, lat) -> corrected built-ground elevation, for extrusion bases
  const groundAt = (lon, lat) =>
    plane.a * ((lon - lon0) * mLon) + plane.b * ((lat - lat0) * mLat) + plane.c;

  window.__field = { cells: good, stats, plane, offset, groundAt, skyline, steps, lon0, lat0, cols, rows };
  console.log('[Field] Data on window.__field. groundAt(lon,lat) returns built-ground elevation.');
  return stats;
};

console.log('[Field v3] Loaded. Run:  await field()');
