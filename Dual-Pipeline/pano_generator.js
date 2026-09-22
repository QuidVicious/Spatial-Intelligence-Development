// ============================================================
// PANORAMA GENERATOR  v1
//
// Captures six 90-degree cube faces from the current camera
// position and reprojects them to a 2:1 equirectangular
// panorama at Marble's recommended 2560 x 1280.
//
// Paste into the console with the viewfinder loaded, park the
// camera where you want the observer to stand, then:
//
//     await pano()                 // 2560 x 1280, centred on current heading
//     await pano({ centerNorth: true })
//     await pano({ faceSize: 1536, width: 4096 })
//     await pano({ debugFaces: true })   // also download the 6 raw faces
//
// Result is downloaded as a PNG and left on window.__pano.
// ============================================================

window.pano = async function (opts = {}) {
  const faceSize   = opts.faceSize   || 1024;   // px per cube face
  const outW       = opts.width      || 2560;   // Marble recommends 2560 wide
  const outH       = Math.round(outW / 2);      // 2:1 equirectangular
  const settleMs   = opts.settleMs   || 900;    // per-face tile settle time
  const maxWaitMs  = opts.maxWaitMs  || 8000;   // per-face tile load ceiling
  const centerNorth= !!opts.centerNorth;
  const debugFaces = !!opts.debugFaces;

  const scene  = viewer.scene;
  const canvas = viewer.canvas;
  const container = document.getElementById('cesiumContainer');
  if (!container) { console.error('[Pano] cesiumContainer not found'); return null; }

  // ---- remember everything we are about to change ----------
  const saved = {
    position: viewer.camera.position.clone(),
    heading:  viewer.camera.heading,
    pitch:    viewer.camera.pitch,
    roll:     viewer.camera.roll,
    fov:      scene.camera.frustum.fov,
    cssW:     container.style.width,
    cssH:     container.style.height,
    cssPos:   container.style.position
  };
  const centerHeading = centerNorth ? 0 : Cesium.Math.toDegrees(saved.heading);

  // Six captures. Bases are in local ENU: x = East, y = North, z = Up.
  // right = cross(dir, up), which matches Cesium's screen-right for these
  // heading/pitch combinations.
  const FACES = [
    { name: 'north', heading: 0,   pitch: 0,   dir: [0, 1, 0],  up: [0, 0, 1],  right: [1, 0, 0] },
    { name: 'east',  heading: 90,  pitch: 0,   dir: [1, 0, 0],  up: [0, 0, 1],  right: [0, -1, 0] },
    { name: 'south', heading: 180, pitch: 0,   dir: [0, -1, 0], up: [0, 0, 1],  right: [-1, 0, 0] },
    { name: 'west',  heading: 270, pitch: 0,   dir: [-1, 0, 0], up: [0, 0, 1],  right: [0, 1, 0] },
    { name: 'up',    heading: 0,   pitch: 90,  dir: [0, 0, 1],  up: [0, -1, 0], right: [1, 0, 0] },
    { name: 'down',  heading: 0,   pitch: -90, dir: [0, 0, -1], up: [0, 1, 0],  right: [1, 0, 0] }
  ];

  function tilesSettled() {
    let ok = true;
    if (scene.globe && scene.globe.show) ok = ok && scene.globe.tilesLoaded;
    for (let i = 0; i < scene.primitives.length; i++) {
      const p = scene.primitives.get(i);
      if (p instanceof Cesium.Cesium3DTileset && p.show) ok = ok && p.tilesLoaded;
    }
    return ok;
  }

  async function waitForTiles() {
    const t0 = performance.now();
    while (performance.now() - t0 < maxWaitMs) {
      scene.render();
      await new Promise(r => requestAnimationFrame(r));
      if (tilesSettled()) break;
    }
    await new Promise(r => setTimeout(r, settleMs));
    scene.render();
    await new Promise(r => requestAnimationFrame(r));
  }

  console.log(`[Pano] capturing 6 faces at ${faceSize}px, output ${outW} x ${outH}`);

  // ---- square the viewport so 90 deg fov is square ---------
  container.style.width  = faceSize + 'px';
  container.style.height = faceSize + 'px';
  viewer.resize();
  scene.camera.frustum.fov = Cesium.Math.toRadians(90);

  const faceData = [];
  try {
    for (const f of FACES) {
      viewer.camera.setView({
        destination: saved.position,
        orientation: {
          heading: Cesium.Math.toRadians(centerHeading + f.heading),
          pitch:   Cesium.Math.toRadians(f.pitch),
          roll:    0
        }
      });
      await waitForTiles();

      const tmp = document.createElement('canvas');
      tmp.width = faceSize; tmp.height = faceSize;
      tmp.getContext('2d').drawImage(canvas, 0, 0, faceSize, faceSize);
      const ctx = tmp.getContext('2d');
      faceData.push({ ...f, img: ctx.getImageData(0, 0, faceSize, faceSize) });
      console.log(`[Pano]   ${f.name} captured`);

      if (debugFaces) {
        const a = document.createElement('a');
        a.href = tmp.toDataURL('image/png');
        a.download = `pano_face_${f.name}.png`;
        a.click();
      }
    }
  } finally {
    // ---- always restore, even on error --------------------
    container.style.width  = saved.cssW;
    container.style.height = saved.cssH;
    viewer.resize();
    scene.camera.frustum.fov = saved.fov;
    viewer.camera.setView({
      destination: saved.position,
      orientation: { heading: saved.heading, pitch: saved.pitch, roll: saved.roll }
    });
    scene.render();
  }

  // ---- reproject to equirectangular ------------------------
  console.log('[Pano] reprojecting...');
  const out = document.createElement('canvas');
  out.width = outW; out.height = outH;
  const outCtx = out.getContext('2d');
  const outImg = outCtx.createImageData(outW, outH);
  const O = outImg.data;

  const D2R = Math.PI / 180;
  const cH = centerHeading * D2R;

  for (let y = 0; y < outH; y++) {
    const el = (0.5 - (y + 0.5) / outH) * Math.PI;      // +pi/2 top .. -pi/2 bottom
    const cosEl = Math.cos(el), sinEl = Math.sin(el);
    for (let x = 0; x < outW; x++) {
      // azimuth measured clockwise from north, centred on centerHeading
      const az = cH + ((x + 0.5) / outW - 0.5) * 2 * Math.PI;
      const dE = Math.sin(az) * cosEl;
      const dN = Math.cos(az) * cosEl;
      const dU = sinEl;

      let r = 0, g = 0, b = 0;
      for (const f of faceData) {
        const a = dE * f.dir[0] + dN * f.dir[1] + dU * f.dir[2];
        if (a <= 1e-6) continue;
        const sx = (dE * f.right[0] + dN * f.right[1] + dU * f.right[2]) / a;
        if (sx < -1 || sx > 1) continue;
        const sy = (dE * f.up[0] + dN * f.up[1] + dU * f.up[2]) / a;
        if (sy < -1 || sy > 1) continue;

        const px = Math.min(faceSize - 1, Math.max(0, Math.floor((sx + 1) * 0.5 * faceSize)));
        const py = Math.min(faceSize - 1, Math.max(0, Math.floor((1 - sy) * 0.5 * faceSize)));
        const i = (py * faceSize + px) * 4;
        r = f.img.data[i]; g = f.img.data[i + 1]; b = f.img.data[i + 2];
        break;
      }
      const o = (y * outW + x) * 4;
      O[o] = r; O[o + 1] = g; O[o + 2] = b; O[o + 3] = 255;
    }
  }
  outCtx.putImageData(outImg, 0, 0);

  const dataUrl = out.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = `pano_${outW}x${outH}_${Date.now()}.png`;
  a.click();

  const carto = Cesium.Cartographic.fromCartesian(saved.position);
  const meta = {
    width: outW, height: outH, faceSize,
    centerAzimuth_deg: +centerHeading.toFixed(2),
    centerIs: centerNorth ? 'true north' : 'camera heading at capture',
    latitude: +Cesium.Math.toDegrees(carto.latitude).toFixed(6),
    longitude: +Cesium.Math.toDegrees(carto.longitude).toFixed(6),
    ellipsoidHeight_m: +carto.height.toFixed(2)
  };
  console.log('[Pano] done');
  console.table(meta);
  console.log('[Pano] dataURL on window.__pano.dataUrl');

  window.__pano = { dataUrl, meta, canvas: out };
  return meta;
};

console.log('[Pano] Loaded. Park the camera, then run:  await pano()');
