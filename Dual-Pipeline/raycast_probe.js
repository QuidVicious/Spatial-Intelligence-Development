// ============================================================
// RAYCAST HEIGHT-FIELD PROBE
// Paste this whole file into the browser console with the
// viewfinder loaded and the camera parked where you want it.
// Then run:   probe()        or   probe(48, 27)
// ============================================================
//
// Casts a grid of rays through the viewport, reads the depth
// buffer at each, and converts hits to lat / lon / height.
// Prints a summary plus an ASCII height map.
// Raw results are left on window.__probe for reuse.
//
// Requires: Cesium loaded, viewer in scope, 3D tiles rendering.
// ------------------------------------------------------------

window.probe = function (cols = 32, rows = 18, opts = {}) {
  const scene = viewer.scene;

  if (!scene.pickPositionSupported) {
    console.error('[Probe] scene.pickPositionSupported is false. Depth picking unavailable in this browser/context.');
    return null;
  }

  const w = viewer.canvas.clientWidth;
  const h = viewer.canvas.clientHeight;
  const hits = [];
  let misses = 0;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      // sample at cell centers, inset from the frame edge
      const x = ((c + 0.5) / cols) * w;
      const y = ((r + 0.5) / rows) * h;
      const cart3 = scene.pickPosition(new Cesium.Cartesian2(x, y));
      if (!Cesium.defined(cart3)) { misses++; continue; }

      const carto = Cesium.Cartographic.fromCartesian(cart3);
      if (!carto || !Number.isFinite(carto.height)) { misses++; continue; }

      hits.push({
        col: c,
        row: r,
        px: x,
        py: y,
        lon: Cesium.Math.toDegrees(carto.longitude),
        lat: Cesium.Math.toDegrees(carto.latitude),
        height: carto.height,
        cartesian: cart3
      });
    }
  }

  if (!hits.length) {
    console.error('[Probe] No hits. Are tiles loaded and is anything in frame?');
    return null;
  }

  const heights = hits.map(p => p.height).sort((a, b) => a - b);
  const pct = q => heights[Math.min(heights.length - 1, Math.floor(q * heights.length))];

  // Ground estimate: low percentile rather than absolute min,
  // so one bad depth sample can't drag the datum down.
  const ground = opts.groundOverride ?? pct(0.05);

  // Camera position for reference
  const camCarto = Cesium.Cartographic.fromCartesian(viewer.camera.position);

  const stats = {
    grid: `${cols} x ${rows}`,
    rays: cols * rows,
    hits: hits.length,
    misses,
    hitRate: `${((hits.length / (cols * rows)) * 100).toFixed(1)}%`,
    groundEstimate_m: +ground.toFixed(2),
    minHeight_m: +heights[0].toFixed(2),
    medianHeight_m: +pct(0.5).toFixed(2),
    p90Height_m: +pct(0.9).toFixed(2),
    maxHeight_m: +heights[heights.length - 1].toFixed(2),
    maxAboveGround_m: +(heights[heights.length - 1] - ground).toFixed(2),
    p90AboveGround_m: +(pct(0.9) - ground).toFixed(2),
    cameraHeight_m: +camCarto.height.toFixed(2),
    cameraAGL_m: +(camCarto.height - ground).toFixed(2),
    heading_deg: +Cesium.Math.toDegrees(viewer.camera.heading).toFixed(1),
    pitch_deg: +Cesium.Math.toDegrees(viewer.camera.pitch).toFixed(1)
  };

  console.log('%c[Probe] Height field summary', 'font-weight:bold');
  console.table(stats);

  // ---- ASCII height map -------------------------------------
  // Relative to ground estimate. Row 0 = top of frame.
  const span = Math.max(1, heights[heights.length - 1] - ground);
  const ramp = ' .:-=+*#%@';
  const grid = Array.from({ length: rows }, () => Array(cols).fill(' '));
  for (const p of hits) {
    const t = Math.max(0, Math.min(1, (p.height - ground) / span));
    grid[p.row][p.col] = ramp[Math.min(ramp.length - 1, Math.floor(t * ramp.length))];
  }
  console.log(
    '[Probe] Height above ground, low to high: "' + ramp + '"\n' +
    grid.map(r => r.join('')).join('\n')
  );

  // ---- Per-column skyline -----------------------------------
  // Highest hit in each screen column, useful for reading rooflines.
  const skyline = [];
  for (let c = 0; c < cols; c++) {
    const col = hits.filter(p => p.col === c);
    if (!col.length) { skyline.push(null); continue; }
    skyline.push(+(Math.max(...col.map(p => p.height)) - ground).toFixed(1));
  }
  console.log('[Probe] Per-column max height above ground (left to right):');
  console.log(skyline.join('  '));

  window.__probe = { hits, stats, ground, skyline, cols, rows };
  console.log('[Probe] Raw data on window.__probe');
  return stats;
};

console.log('[Probe] Loaded. Run probe() or probe(48, 27).');
