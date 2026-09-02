// ============================================================
// TERRAIN ACCESS TEST
// Answers one question: can we get GROUND elevation underneath
// a building, or only the top surface of whatever is there?
//
// Paste into the console with the viewfinder loaded and the
// camera looking at a terrace, then run:
//     terrainTest()
// ============================================================

window.terrainTest = async function () {
  const scene = viewer.scene;
  const out = {};

  // ---- 1. what is currently loaded --------------------------
  const providerName = viewer.terrainProvider
    ? viewer.terrainProvider.constructor.name
    : '(none)';
  const isEllipsoidOnly =
    providerName === 'EllipsoidTerrainProvider' || providerName === '(none)';

  out.terrainProvider = providerName;
  out.terrainIsFlatEllipsoid = isEllipsoidOnly;
  out.pickPositionSupported = scene.pickPositionSupported;
  out.sampleHeightSupported = scene.sampleHeightSupported;
  out.clampToHeightSupported = scene.clampToHeightSupported;
  out.primitiveCount = scene.primitives.length;

  // find the Google photorealistic tileset so we can exclude it
  let googleTileset = null;
  for (let i = 0; i < scene.primitives.length; i++) {
    const p = scene.primitives.get(i);
    if (p instanceof Cesium.Cesium3DTileset) { googleTileset = p; break; }
  }
  out.foundTileset = !!googleTileset;

  console.log('%c[TerrainTest] Environment', 'font-weight:bold');
  console.table(out);

  if (isEllipsoidOnly) {
    console.warn(
      '[TerrainTest] No real terrain provider is loaded, so there is nothing ' +
      'beneath the photogrammetry mesh to hit. Load Cesium World Terrain and ' +
      're-run:\n\n' +
      "  viewer.terrainProvider = await Cesium.createWorldTerrainAsync();\n"
    );
  }

  // ---- 2. pick a test point: centre of the frame -------------
  const w = viewer.canvas.clientWidth;
  const h = viewer.canvas.clientHeight;
  const centre = new Cesium.Cartesian2(w * 0.5, h * 0.45);
  const surfaceCart3 = scene.pickPosition(centre);

  if (!Cesium.defined(surfaceCart3)) {
    console.error('[TerrainTest] Nothing under the centre of the frame. Aim at a building and re-run.');
    return null;
  }
  const surfaceCarto = Cesium.Cartographic.fromCartesian(surfaceCart3);
  const lon = Cesium.Math.toDegrees(surfaceCarto.longitude);
  const lat = Cesium.Math.toDegrees(surfaceCarto.latitude);

  const results = {
    testPoint: `${lat.toFixed(6)}, ${lon.toFixed(6)}`,
    surfaceHeight_m: +surfaceCarto.height.toFixed(2)
  };

  // ---- 3. method A: sampleHeightMostDetailed (top surface) ---
  try {
    const probe = Cesium.Cartographic.fromDegrees(lon, lat);
    const r = await scene.sampleHeightMostDetailed([probe]);
    results.sampleHeight_m = (r && r[0] && Number.isFinite(r[0].height))
      ? +r[0].height.toFixed(2) : 'undefined';
  } catch (e) {
    results.sampleHeight_m = 'ERROR: ' + e.message;
  }

  // ---- 4. method B: globe terrain height at the same lon/lat -
  try {
    const g = viewer.scene.globe.getHeight(Cesium.Cartographic.fromDegrees(lon, lat));
    results.globeGetHeight_m = Number.isFinite(g) ? +g.toFixed(2) : 'undefined';
  } catch (e) {
    results.globeGetHeight_m = 'ERROR: ' + e.message;
  }

  // ---- 5. method C: sampleTerrainMostDetailed (true terrain) -
  try {
    if (!isEllipsoidOnly) {
      const t = await Cesium.sampleTerrainMostDetailed(
        viewer.terrainProvider, [Cesium.Cartographic.fromDegrees(lon, lat)]
      );
      results.sampleTerrain_m = (t && t[0] && Number.isFinite(t[0].height))
        ? +t[0].height.toFixed(2) : 'undefined';
    } else {
      results.sampleTerrain_m = 'n/a (flat ellipsoid)';
    }
  } catch (e) {
    results.sampleTerrain_m = 'ERROR: ' + e.message;
  }

  // ---- 6. method D: downward ray, tileset excluded -----------
  try {
    const startCarto = Cesium.Cartographic.fromDegrees(lon, lat, surfaceCarto.height + 300);
    const start = Cesium.Cartographic.toCartesian(startCarto);
    const down = Cesium.Cartesian3.normalize(
      Cesium.Cartesian3.negate(
        Cesium.Ellipsoid.WGS84.geodeticSurfaceNormalCartographic(startCarto, new Cesium.Cartesian3()),
        new Cesium.Cartesian3()
      ),
      new Cesium.Cartesian3()
    );
    const ray = new Cesium.Ray(start, down);
    const exclude = googleTileset ? [googleTileset] : [];
    const hit = scene.pickFromRay(ray, exclude);
    if (hit && hit.position) {
      const c = Cesium.Cartographic.fromCartesian(hit.position);
      results.rayExcludingTileset_m = +c.height.toFixed(2);
      results.rayHitObject = hit.object ? (hit.object.constructor?.name || 'object') : 'terrain/globe';
    } else {
      results.rayExcludingTileset_m = 'no hit';
    }
  } catch (e) {
    results.rayExcludingTileset_m = 'ERROR: ' + e.message;
  }

  console.log('%c[TerrainTest] Height at one point, five ways', 'font-weight:bold');
  console.table(results);

  console.log(
    '[TerrainTest] How to read this:\n' +
    '  surfaceHeight / sampleHeight  = top of whatever is there (roof, if aimed at a building)\n' +
    '  globeGetHeight / sampleTerrain = bare terrain, no buildings\n' +
    '  rayExcludingTileset            = first thing hit going down with the mesh ignored\n\n' +
    'If you aimed at a ROOF and the terrain values come back roughly street level,\n' +
    'ground-under-building works and the two-pass grid is viable.\n' +
    'If terrain matches the roof height, or is undefined, it does not.'
  );

  window.__terrainTest = { env: out, results };
  return results;
};

console.log('[TerrainTest] Loaded. Aim at a BUILDING, then run terrainTest().');
