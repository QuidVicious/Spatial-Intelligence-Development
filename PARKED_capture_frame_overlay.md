# Parked: capture frame on the pano, and Fit pano to capture

Removed 2026-10-12, to come back as a polish item (Pro Mode) once LSA and the Cesium pipeline are fully joined and testing well. Design and reasons: DECISIONS.md, 2026-10-09, "The capture's frame on the pano, and Fit pano to capture".

To restore: put the HTML block back in place of the plain `sv-preview` image in the Street View card, the CSS into the style block, and the JS before `svUseKeystonePano` in pipeline.js. Then re-add the hooks:
- `svProbing` guard at the top of `updateTelemetryHUD()` and `onCameraSettle()` (`if (!viewer || svProbing) return;`)
- `if (svState) svDrawFrame();` after `onCesiumReady()`
- `svDrawFrame();` at the end of `svShowPreview()`, and `fitted` shown in its meta line
- `svState.fitted = false;` in `svApplyOverride()`; `svClearFrame('');` in `svReset()`
- `"fitted"` back in the keystone streetview record in server.py

Untested against live Cesium when parked.

## HTML (Street View card)

```html
      <div class="sv-frame" id="sv-frame-box">
        <img id="sv-preview" alt="Street View preview" style="display: none; width: 100%; aspect-ratio: 16 / 9; object-fit: fill; background: var(--slate-2); border-radius: 6px; border: 1px solid var(--panel-border);" />
        <svg id="sv-frame-svg" viewBox="0 0 1600 900" preserveAspectRatio="none" aria-hidden="true"></svg>
      </div>
      <div class="sv-frame-tools">
        <label class="live-toggle-wrapper"><input type="checkbox" id="chk-sv-frame" checked onchange="svDrawFrame()"> Show what the capture frames</label>
        <button class="toggle-btn" id="btn-sv-fit" onclick="svFitToCapture()" title="Aim the pano and set its field of view so the capture's whole frame fits inside it">FIT PANO TO CAPTURE</button>
      </div>
      <div class="hint" id="sv-frame-note"></div>
```

## CSS

```css
  /* the capture's frame drawn on the pano: grey outside, frame lines and corner marks */
  .sv-frame { position: relative; margin-top: 8px; }
  .sv-frame img { display: block; }
  #sv-frame-svg { position: absolute; inset: 1px; width: calc(100% - 2px); height: calc(100% - 2px); pointer-events: none; border-radius: 5px; }
  .sv-frame-tools { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
  .sv-frame-tools .toggle-btn { padding: 6px 10px; }
```

## JavaScript (pipeline.js)

```js
    // ---------------- The capture's frame on the pano ----------------
    // The capture and the pano are taken from different places, so the capture's frame is not a
    // rectangle on the pano. Cesium is put briefly at the capture camera (the run's saved view),
    // finds the 3D surface points along the frame's four edges, and each point is projected into
    // the pano from the pano's own position. The outline is exact where it touches surfaces;
    // where an edge looks at sky it follows the direction. Nearer objects shift more between
    // the two viewpoints, which is why the outline can be skewed.
    const SV_CAMERA_HEIGHT_M = 2.5;   // Street View camera above the road, roughly
    const SV_EDGE_STEPS = 8;          // points per edge; corners are 0, 8, 16, 24
    let svProbing = false;            // true while Cesium is briefly at a capture pose
    const svPerimeterCache = new Map();
    const svGroundCache = new Map();
    let svFrameToken = 0;

    function svFrameNote(msg, color) {
      const el = document.getElementById('sv-frame-note');
      if (!el) return;
      el.style.color = color || '';
      el.textContent = msg;
    }
    function svClearFrame(note) {
      const svg = document.getElementById('sv-frame-svg');
      if (svg) svg.innerHTML = '';
      if (note !== undefined) svFrameNote(note);
    }

    function svCaptureView(run) {
      const view = run && savedViews.find(v => v.id === run.saved_view_id);
      return view && view.camera ? view : null;
    }

    async function svWaitTiles(maxMs) {
      const scene = viewer.scene, t0 = performance.now();
      while (performance.now() - t0 < maxMs) {
        scene.render();
        await new Promise(r => requestAnimationFrame(r));
        let ok = true;
        for (let i = 0; i < scene.primitives.length; i++) {
          const pr = scene.primitives.get(i);
          if (pr instanceof Cesium.Cesium3DTileset && pr.show) ok = ok && pr.tilesLoaded;
        }
        if (ok) break;
      }
      await new Promise(r => setTimeout(r, 250));
      scene.render();
      await new Promise(r => requestAnimationFrame(r));
    }

    // The capture frame's edge as 3D points, clockwise from the top-left corner.
    async function svCapturePerimeter(view) {
      const key = `${view.id}|${view.updated_utc || ''}`;
      if (svPerimeterCache.has(key)) return svPerimeterCache.get(key);
      const cam = viewer.camera, scene = viewer.scene, c = view.camera;
      const saved = { pos: cam.position.clone(), h: cam.heading, p: cam.pitch, r: cam.roll, fov: cam.frustum.fov };
      const subjShown = subjectEntity ? subjectEntity.show : null;
      const pts = [];
      svProbing = true;
      try {
        if (subjectEntity) subjectEntity.show = false;
        if (c.fov_deg) cam.frustum.fov = Cesium.Math.toRadians(c.fov_deg);
        cam.setView({
          destination: new Cesium.Cartesian3(c.x, c.y, c.z),
          orientation: { heading: Cesium.Math.toRadians(c.heading_deg), pitch: Cesium.Math.toRadians(c.pitch_deg), roll: Cesium.Math.toRadians(c.roll_deg || 0) }
        });
        await svWaitTiles(6000);
        const w = scene.canvas.clientWidth, h = scene.canvas.clientHeight, N = SV_EDGE_STEPS, m = 1;
        const win = [];
        for (let i = 0; i < N; i++) win.push([m + (w - 2 * m) * i / N, m]);              // top, left to right
        for (let i = 0; i < N; i++) win.push([w - m, m + (h - 2 * m) * i / N]);          // right, top to bottom
        for (let i = 0; i < N; i++) win.push([w - m - (w - 2 * m) * i / N, h - m]);      // bottom, right to left
        for (let i = 0; i < N; i++) win.push([m, h - m - (h - 2 * m) * i / N]);          // left, bottom to top
        for (const [x, y] of win) {
          const wp = new Cesium.Cartesian2(x, y);
          let p = null;
          try { p = scene.pickPositionSupported ? scene.pickPosition(wp) : null; } catch (e) { p = null; }
          let hit = !!p;
          if (p) {
            const d = Cesium.Cartesian3.distance(cam.position, p);
            if (!Number.isFinite(d) || d > 5000) { p = null; hit = false; }
          }
          if (!p) p = Cesium.Ray.getPoint(cam.getPickRay(wp), 2000, new Cesium.Cartesian3());   // sky: direction only
          pts.push({ x: p.x, y: p.y, z: p.z, hit });
        }
      } finally {
        cam.frustum.fov = saved.fov;
        cam.setView({ destination: saved.pos, orientation: { heading: saved.h, pitch: saved.p, roll: saved.r } });
        if (subjectEntity && subjShown !== null) subjectEntity.show = subjShown;
        scene.render();
        svProbing = false;
        updateTelemetryHUD();   // the dial and strip show the real camera again
      }
      const out = { pts, hits: pts.filter(p => p.hit).length };
      svPerimeterCache.set(key, out);
      return out;
    }

    // Where the Street View camera stood: the pano's position, on the ground, plus camera height.
    async function svPanoPosition() {
      if (!Number.isFinite(svState.lat) || !Number.isFinite(svState.lon)) {
        const subj = svSubjectFor(selectedReplayRun()) || { lat: 0, lon: 0 };
        try { const m = await svFetchMeta(subj, svState.pano_id); svState.lat = m.lat; svState.lon = m.lon; }
        catch (e) { return null; }
      }
      const key = `${svState.lat},${svState.lon}`;
      let g = svGroundCache.get(key);
      if (!Number.isFinite(g)) {
        const at = Cesium.Cartographic.fromDegrees(svState.lon, svState.lat);
        try { const [r] = await Cesium.sampleTerrainMostDetailed(viewer.terrainProvider, [at]); g = r.height; } catch (e) {}   // bare earth: not a car or a tree
        if (!Number.isFinite(g) && viewer.scene.sampleHeightSupported) {
          try { const [r] = await viewer.scene.sampleHeightMostDetailed([Cesium.Cartographic.fromDegrees(svState.lon, svState.lat)]); g = r.height; } catch (e) {}
        }
        if (!Number.isFinite(g)) return null;
        svGroundCache.set(key, g);
      }
      return Cesium.Cartesian3.fromDegrees(svState.lon, svState.lat, g + SV_CAMERA_HEIGHT_M);
    }

    // A world point as seen by the pano camera: bearing and elevation from the pano, and its place
    // in the frame (-1..1 across and up, for a rectilinear view with the card's heading, pitch and FOV).
    function svLook(enuInv, pt) {
      const l = Cesium.Matrix4.multiplyByPoint(enuInv, new Cesium.Cartesian3(pt.x, pt.y, pt.z), new Cesium.Cartesian3());
      const L = Math.hypot(l.x, l.y, l.z) || 1;
      return { d: [l.x / L, l.y / L, l.z / L], az: (Math.atan2(l.x, l.y) / DEG + 360) % 360, el: Math.atan2(l.z, Math.hypot(l.x, l.y)) / DEG };
    }
    function svProject(look, view) {
      const h = view.heading * DEG, p = view.pitch * DEG;
      const f = [Math.sin(h) * Math.cos(p), Math.cos(h) * Math.cos(p), Math.sin(p)];
      const r = [Math.cos(h), -Math.sin(h), 0];
      const u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]];
      const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
      const xc = dot(look.d, r), yc = dot(look.d, u), zc = dot(look.d, f);
      const aspect = view.size === SV_SQUARE ? 1 : SV_ASPECT;
      const th = Math.tan(view.fov * DEG / 2), tv = th / aspect;
      return { sx: (xc / zc) / th, sy: (yc / zc) / tv, front: zc > 0.02 };
    }

    // Everything the overlay and the fit need, or null with the reason in the note.
    async function svFrameData() {
      const run = selectedReplayRun();
      if (!svState || !svState.pano_id) return null;
      if (!viewer) { svFrameNote('Cesium is still loading; the capture frame appears when it is ready.'); return null; }
      const view = svCaptureView(run);
      if (!view) { svFrameNote('This run has no saved view, so the capture camera is unknown and its frame cannot be shown.'); return null; }
      svFrameNote(`Measuring the capture frame in Cesium (${view.name})...`);
      const perim = await svCapturePerimeter(view);
      const P = await svPanoPosition();
      if (!P) { svFrameNote('The pano position or ground height could not be found, so the frame cannot be placed.', '#ff5252'); return null; }
      const enuInv = Cesium.Matrix4.inverse(Cesium.Transforms.eastNorthUpToFixedFrame(P), new Cesium.Matrix4());
      const looks = perim.pts.map(pt => svLook(enuInv, pt));
      let stale = false;
      const made = run && runMadeAt(run), upd = view.updated_utc ? new Date(view.updated_utc) : null;
      if (made && upd && upd - made > 60000) stale = true;
      return { run, view, perim, looks, stale };
    }

    async function svDrawFrame() {
      const token = ++svFrameToken;
      const svg = document.getElementById('sv-frame-svg');
      const img = document.getElementById('sv-preview');
      if (!svg) return;
      if (!document.getElementById('chk-sv-frame').checked || !svState || img.style.display === 'none') { svClearFrame(''); return; }
      let data;
      try { data = await svFrameData(); } catch (e) { console.warn('[SV frame]', e); svClearFrame('The capture frame could not be measured.'); return; }
      if (token !== svFrameToken) return;   // a newer redraw has started
      if (!data) { svg.innerHTML = ''; return; }
      const square = svState.size === SV_SQUARE;
      const W = 1600, H = square ? 1600 : 900;
      svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
      const pr = data.looks.map(l => svProject(l, svState));
      const clampXY = v => Math.max(-20000, Math.min(20000, v));
      const xy = pr.map(q => [clampXY((q.sx + 1) / 2 * W), clampXY((1 - q.sy) / 2 * H)]);
      const behind = pr.filter(q => !q.front).length;
      const names = ['top-left', 'top-right', 'bottom-right', 'bottom-left'];
      const cornerIdx = [0, SV_EDGE_STEPS, 2 * SV_EDGE_STEPS, 3 * SV_EDGE_STEPS];
      const outside = cornerIdx.map((i, k) => (!pr[i].front || Math.abs(pr[i].sx) > 1 || Math.abs(pr[i].sy) > 1) ? names[k] : null).filter(Boolean);
      let html = '';
      if (!behind) {
        const poly = xy.map(p => p.map(v => v.toFixed(1)).join(',')).join(' ');
        html += `<path d="M0,0 H${W} V${H} H0 Z M${xy.map(p => p.map(v => v.toFixed(1)).join(',')).join(' L')} Z" fill="rgba(20,22,21,0.62)" fill-rule="evenodd"/>`;
        html += `<polygon points="${poly}" fill="none" stroke="#e2892b" stroke-width="3" stroke-dasharray="14 8"/>`;
        // viewfinder corner marks: short solid arms along both edges from each corner
        const n = xy.length;
        for (const i of cornerIdx) {
          if (!names[cornerIdx.indexOf(i)] || outside.includes(names[cornerIdx.indexOf(i)])) continue;
          const [cx, cy] = xy[i];
          for (const j of [(i + 1) % n, (i - 1 + n) % n]) {
            const [ox, oy] = xy[j], len = Math.hypot(ox - cx, oy - cy) || 1, k = Math.min(1, 70 / len);
            html += `<line x1="${cx.toFixed(1)}" y1="${cy.toFixed(1)}" x2="${(cx + (ox - cx) * k).toFixed(1)}" y2="${(cy + (oy - cy) * k).toFixed(1)}" stroke="#e2892b" stroke-width="9" stroke-linecap="square"/>`;
          }
        }
      } else {
        // part of the frame is behind the pano camera: draw only the parts in front, no grey
        let seg = [];
        const flush = () => { if (seg.length > 1) html += `<polyline points="${seg.join(' ')}" fill="none" stroke="#e2892b" stroke-width="3" stroke-dasharray="14 8"/>`; seg = []; };
        pr.forEach((q, i) => { if (q.front) seg.push(xy[i].map(v => v.toFixed(1)).join(',')); else flush(); });
        flush();
      }
      svg.innerHTML = html;
      const parts = [];
      parts.push(outside.length ? `Corners outside the pano: ${outside.join(', ')}. FIT PANO TO CAPTURE brings them in.` : 'All four corners of the capture are inside the pano.');
      if (behind) parts.push('Part of the capture frame is behind this pano\'s camera.');
      parts.push(`The frame lands exactly on surfaces it touches (${data.perim.hits} of ${data.perim.pts.length} edge points); nearer things shift between the two viewpoints.`);
      if (data.stale) parts.push(`The view "${data.view.name}" was re-saved after this run, so the frame may not match its capture.`);
      svFrameNote(parts.join(' '), outside.length || behind || data.stale ? '#ffb74d' : '');
    }

    // Aim the pano at the capture's frame and widen it until all of the frame fits, with a small margin.
    async function svFitToCapture() {
      if (!svState) { setSvStatus('Set a pano first: paste a Maps link or Propose.', '#ff5252'); return; }
      let data;
      try { data = await svFrameData(); }
      catch (e) { console.warn('[SV fit]', e); setSvStatus('The capture frame could not be measured.', '#ff5252'); svFrameNote('The capture frame could not be measured.', '#ff5252'); return; }
      if (!data) return;
      const h0 = svState.heading;
      const rel = data.looks.map(l => ((l.az - h0 + 540) % 360) - 180);
      const els = data.looks.map(l => l.el);
      const minA = Math.min(...rel), maxA = Math.max(...rel), minE = Math.min(...els), maxE = Math.max(...els);
      const margin = 3;
      const view = { heading: ((h0 + (minA + maxA) / 2) % 360 + 360) % 360, pitch: (minE + maxE) / 2, size: SV_SIZE };
      const needV = (maxE - minE) / 2 + margin;
      view.fov = Math.max(maxA - minA + 2 * margin, 2 * Math.atan(Math.tan(Math.min(needV, 85) * DEG) * SV_ASPECT) / DEG);
      const fits = v => data.looks.every(l => { const q = svProject(l, v); return q.front && Math.abs(q.sx) <= 0.97 && Math.abs(q.sy) <= 0.97; });
      for (let i = 0; i < 40 && view.fov < 120 && !fits({ ...view, fov: Math.min(view.fov, 120) }); i++) view.fov *= 1.04;
      const capped = view.fov > 120 || !fits({ ...view, fov: Math.min(view.fov, 120) });
      view.fov = Math.max(10, Math.min(120, view.fov));
      svState = { ...svState, heading: r2(view.heading), pitch: r2(view.pitch), fov: r1(view.fov), size: SV_SIZE,
                  source_url: null, maps_fov: null, fitted: true };
      svFillInputs(); svShowPreview();
      setSvStatus(capped
        ? `Fitted as far as the API allows (120° across): from this pano the capture's frame is wider than that, so its edges are still cut. A pano farther back would fit it.`
        : `Fitted to the capture: heading ${svState.heading}°, pitch ${svState.pitch}°, ${svState.fov}° across (Maps ${r1(mapsFromHfov(svState.fov))}°).`,
        capped ? '#ffb74d' : 'var(--accent-cyan)');
    }

```
