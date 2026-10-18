/*
 * Cesium pipeline client for the combined LSA Studio page (Stage 2).
 * Ported from Viewfinder's page script. Every call goes to the pipeline server
 * on port 8000; LSA Studio's own calls stay on this page's server (8001).
 */
const PIPE = `${location.protocol}//${location.hostname}:8000`;
    let viewer = null;
    let currentProvider = 'GEMINI';
    let currentLightingMode = 'SOLAR';
    let tilesLoaded = false;
    let terrainLoaded = false;
    let googleTileset = null;
    let lastGroundM = null;
    let currentWeatherMode = 'AUTO';

    async function initApp() {
      const now = new Date();
      document.getElementById('input-date').value = now.toISOString().split('T')[0];
      const currentHourDecimal = now.getHours() + now.getMinutes() / 60.0;
      document.getElementById('input-time-slider').value = currentHourDecimal.toFixed(2);
      updateSliderDisplay(currentHourDecimal);

      try {
        const configResp = await fetch(PIPE + '/api/config');
        if (configResp.ok) {
          const cfg = await configResp.json();
          if (cfg.cesium_ion_token) Cesium.Ion.defaultAccessToken = cfg.cesium_ion_token;
        }
      } catch (err) {}

      viewer = new Cesium.Viewer('cesiumContainer', {
        contextOptions: { webgl: { preserveDrawingBuffer: true } },
        baseLayer: false,
        baseLayerPicker: false, geocoder: false, animation: false, timeline: false, fullscreenButton: false, vrButton: false, infoBox: false, selectionIndicator: false, navigationHelpButton: false
      });

      viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(-3.211036, 55.953492, 250.0), orientation: { heading: Cesium.Math.toRadians(315.0), pitch: Cesium.Math.toRadians(-25.0), roll: 0.0 } });

      try {
        if (!Cesium.Ion.defaultAccessToken) {
          console.error('[Tiles] No Cesium Ion token reached the client. Check /api/config and CESIUM_ION_TOKEN in .env');
        }
        googleTileset = await Cesium.createGooglePhotorealistic3DTileset();
        viewer.scene.primitives.add(googleTileset);
        tilesLoaded = true;
        console.log('[Tiles] Google Photorealistic 3D Tiles loaded.');
      } catch (e) {
        console.error('[Tiles] FAILED to load Google Photorealistic 3D Tiles:', e);
      }
      setTileStatusHUD(tilesLoaded);

      // Bare-earth terrain, loaded for HEIGHT SAMPLING ONLY.
      // The globe is hidden so it cannot z-fight with the photogrammetry mesh;
      // Cesium.sampleTerrainMostDetailed queries the provider directly and does
      // not require the globe to be rendered. Toggle with setGlobe(true).
      try {
        viewer.terrainProvider = await Cesium.createWorldTerrainAsync();
        terrainLoaded = true;
        viewer.scene.globe.show = false;
        console.log('[Terrain] Cesium World Terrain loaded (globe hidden, sampling only).');
      } catch (e) {
        console.error('[Terrain] FAILED to load Cesium World Terrain:', e);
      }

      viewer.camera.percentageChanged = 0.01;
      viewer.camera.changed.addEventListener(updateTelemetryHUD);
      viewer.camera.moveEnd.addEventListener(onCameraSettle);
      loadSavedViews();
      loadReplayRuns();
      initSubjectPicking();
      pollSeries();   // pick up a series that is already running on the server
      updateTelemetryHUD();
      syncCesiumTime();
      onCameraSettle();
      if (typeof onCesiumReady === 'function') onCesiumReady();
    }

    function toggleLiveTime(isLive) {
      const dateInput = document.getElementById('input-date');
      const timeSlider = document.getElementById('input-time-slider');
      if (isLive) {
        dateInput.classList.add('disabled-el'); timeSlider.classList.add('disabled-el');
        const now = new Date();
        dateInput.value = now.toISOString().split('T')[0];
        timeSlider.value = (now.getHours() + now.getMinutes() / 60.0).toFixed(2);
        updateSliderDisplay(timeSlider.value);
        syncCesiumTime();
      } else {
        dateInput.classList.remove('disabled-el'); timeSlider.classList.remove('disabled-el');
      }
    }

    function setProvider(prov) {
      currentProvider = prov;
      const isMarble = (prov === 'WORLD_LABS');
      document.getElementById('btn-prov-gemini').classList.toggle('active', !isMarble);
      document.getElementById('btn-prov-marble').classList.toggle('active', isMarble);
      document.getElementById('btn-synthesize-action').textContent = isMarble ? 'Synthesize 3D world' : 'Synthesize';
      document.getElementById('marble-options').style.display = isMarble ? 'block' : 'none';
      document.getElementById('gemini-options').style.display = isMarble ? 'none' : 'block';
    }

    function onViewScopeChange(val) { document.getElementById('view-scope-label').textContent = val; }
    function onTimeSliderChange(val) { updateSliderDisplay(parseFloat(val)); syncCesiumTime(); }
    
    function updateSliderDisplay(val) {
      const h = Math.floor(val); const m = Math.floor((val - h) * 60);
      const hhmm = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      document.getElementById('slider-time-display').textContent = hhmm;
      const lsaTime = document.getElementById('f-time');
      if (lsaTime) { lsaTime.value = hhmm; if (typeof onChange === 'function') onChange(); }
    }

    // The date and time controls mean local time AT THE LOCATION, as the pipeline's lighting engine reads them.
    // Cesium wants UTC, so convert with the location's time zone (from /api/weather), including daylight saving
    // on the chosen date. Until the zone is known, fall back to an offset from longitude.
    let locationTZ = null, locationLon = null;
    function tzOffsetMs(tz, utcMs) {
      const parts = {};
      new Intl.DateTimeFormat('en-US', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit' }).formatToParts(new Date(utcMs)).forEach(p => { parts[p.type] = p.value; });
      const asUTC = Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour % 24, +parts.minute, +parts.second);
      return asUTC - Math.floor(utcMs / 1000) * 1000;
    }
    function localToUtcMs(dateStr, hh, mm) {
      const [y, mo, d] = dateStr.split('-').map(Number);
      const guess = Date.UTC(y, mo - 1, d, hh, mm);
      if (locationTZ) {
        try { const off = tzOffsetMs(locationTZ, guess - tzOffsetMs(locationTZ, guess)); return guess - off; }
        catch (e) { console.warn('[Time] zone', locationTZ, 'unusable:', e); }
      }
      return guess - Math.round((locationLon || 0) / 15) * 3600e3;
    }
    // Test switch (2026-10-13): Cesium's own sun and cast shadows for the strip's date and time.
    // Google's tiles carry the light of their aerial photos; this shows whether Cesium can lay the right
    // sun over them. Google's tiles are unlit, so expect cast shadows rather than shading by face direction.
    function setSunShadows(on) {
      if (!viewer) return;
      viewer.scene.light = new Cesium.SunLight();
      viewer.shadows = !!on;
      if (on) {
        viewer.shadowMap.softShadows = true;
        viewer.shadowMap.darkness = 0.35;
        viewer.shadowMap.maximumDistance = 1500.0;
      }
      if (googleTileset) googleTileset.shadows = on ? Cesium.ShadowMode.ENABLED : Cesium.ShadowMode.DISABLED;
      syncCesiumTime();
      viewer.scene.requestRender();
      console.log(`[Sun] Cesium sun and shadows ${on ? 'on' : 'off'} at`, Cesium.JulianDate.toIso8601(viewer.clock.currentTime));
    }

    function syncCesiumTime() {
      if (!viewer) return;
      const dateStr = document.getElementById('input-date').value;
      const [hh, mm] = document.getElementById('slider-time-display').textContent.split(':').map(Number);
      if (!dateStr || isNaN(hh)) return;
      viewer.clock.currentTime = Cesium.JulianDate.fromDate(new Date(localToUtcMs(dateStr, hh, mm || 0)));
    }

    function setTileStatusHUD(ok) {
      const el = document.getElementById('tile-status');
      if (!el) return;
      el.textContent = ok ? 'TILES: 3D OK' : 'TILES: FAILED (2D IMAGERY ONLY)';
      el.style.color = ok ? 'var(--accent-cyan)' : '#ff5252';
    }

    function updateTelemetryHUD() {
      if (!viewer) return;
      const cart = Cesium.Cartographic.fromCartesian(viewer.camera.position);
      document.getElementById('telemetry-coords').textContent = `${Cesium.Math.toDegrees(cart.latitude).toFixed(5)}, ${Cesium.Math.toDegrees(cart.longitude).toFixed(5)}`;
      document.getElementById('telemetry-alt').textContent = lastGroundM === null
        ? `${cart.height.toFixed(1)} m (ellip)`
        : `${(cart.height - lastGroundM).toFixed(1)} m AGL`;
      document.getElementById('telemetry-heading-pitch').textContent =
        `${Cesium.Math.toDegrees(viewer.camera.heading).toFixed(1)}\u00b0 / ${Cesium.Math.toDegrees(viewer.camera.pitch).toFixed(1)}\u00b0`;
      document.getElementById('telemetry-fov').textContent =
        `${Cesium.Math.toDegrees(viewer.camera.frustum.fov || 0.785).toFixed(1)}\u00b0`;
      if (typeof liveDialUpdate === 'function') liveDialUpdate();
    }

    async function computeAltitudeAGL(cart) {
      const ellipsoidHeight = cart.height;
      if (tilesLoaded && viewer.scene.sampleHeightSupported) {
        try {
          const probe = Cesium.Cartographic.fromRadians(cart.longitude, cart.latitude);
          const results = await viewer.scene.sampleHeightMostDetailed([probe]);
          const g = results && results[0] ? results[0].height : undefined;
          if (Number.isFinite(g)) {
            lastGroundM = g;
            return { agl: ellipsoidHeight - g, ground_m: g, method: 'TILESET_SAMPLE' };
          }
        } catch (e) {
          console.warn('[AGL] sampleHeightMostDetailed failed:', e);
        }
      }
      return { agl: ellipsoidHeight, ground_m: null, method: 'ELLIPSOID_FALLBACK' };
    }

    let settleTimeout = null;
    function onCameraSettle() {
      if (!viewer) return;
      clearTimeout(settleTimeout);
      settleTimeout = setTimeout(async () => {
        const cart = Cesium.Cartographic.fromCartesian(viewer.camera.position);
        const lat = Cesium.Math.toDegrees(cart.latitude);
        const lon = Cesium.Math.toDegrees(cart.longitude);
        fetchLocationHUD(lat, lon); fetchLiveWeatherHUD(lat, lon);
      }, 400);
    }

    async function fetchLocationHUD(lat, lon) {
      try { const resp = await fetch(`${PIPE}/api/geocode?lat=${lat}&lon=${lon}`); if (resp.ok) { const data = await resp.json(); document.getElementById('current-location-text').textContent = data.address || `${lat.toFixed(4)}°, ${lon.toFixed(4)}°`; } } catch (err) {}
    }

    async function fetchLiveWeatherHUD(lat, lon) {
      locationLon = lon;
      try {
        const resp = await fetch(`${PIPE}/api/weather?lat=${lat}&lon=${lon}`);
        if (resp.ok) {
          const w = await resp.json();
          document.getElementById('hud-live-weather-text').textContent = `${w.label} • ${Number(w.temperature_c).toFixed(1)}°C`;
          // A reply without a source is the server's fallback when the weather service failed: its "UTC" is a placeholder.
          const tz = w.source && w.timezone ? w.timezone : null;
          if (tz !== locationTZ) { locationTZ = tz; syncCesiumTime(); }
          const disp = document.getElementById('slider-time-display');
          if (disp) disp.title = locationTZ ? `Local time at the location (${locationTZ})` : 'Local time at the location (zone not yet known)';
        }
      } catch (e) {}
    }

    function setLightingMode(mode) { currentLightingMode = mode; document.getElementById('btn-mode-solar').classList.toggle('active', mode === 'SOLAR'); document.getElementById('btn-mode-floodlight').classList.toggle('active', mode === 'FLOODLIGHT'); }
    function setWeatherMode(mode, elem) { currentWeatherMode = mode; document.querySelectorAll('.weather-btn').forEach(b => b.classList.remove('active')); if (elem) elem.classList.add('active'); }
    function closeDrawer() {}

    async function goToPlace() {
      const q = document.getElementById('input-place-search').value.trim();
      const status = document.getElementById('search-status');
      if (!q) return;
      status.style.color = 'var(--text-muted)';
      status.textContent = 'Searching...';
      try {
        const resp = await fetch(`${PIPE}/api/search?q=${encodeURIComponent(q)}`);
        if (!resp.ok) {
          status.style.color = '#ff5252';
          status.textContent = 'No match found.';
          return;
        }
        const d = await resp.json();
        status.style.color = 'var(--accent-cyan)';
        status.textContent = d.address || `${d.latitude.toFixed(5)}, ${d.longitude.toFixed(5)}`;
        if (typeof setPlace === 'function') setPlace(d.address);
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(d.longitude, d.latitude, 400.0),
          orientation: { heading: 0.0, pitch: Cesium.Math.toRadians(-35), roll: 0.0 },
          duration: 2.5
        });
      } catch (e) {
        status.style.color = '#ff5252';
        status.textContent = 'Search failed.';
      }
    }

    // ---------------- Saved Views ----------------
    let savedViews = [];
    let activeSavedView = null;  // last view reached with GO

    // A capture is tagged with a saved view only if the camera is still exactly there.
    function cameraMatchesView(v) {
      if (!v || !viewer) return false;
      const c = v.camera, cam = viewer.camera;
      const dist = Cesium.Cartesian3.distance(cam.position, new Cesium.Cartesian3(c.x, c.y, c.z));
      const angDiff = (a, b) => Math.abs(((a - b + 540) % 360) - 180);
      return dist < 0.5
        && angDiff(Cesium.Math.toDegrees(cam.heading), c.heading_deg) < 0.1
        && angDiff(Cesium.Math.toDegrees(cam.pitch), c.pitch_deg) < 0.1;
    }

    function setViewsStatus(msg, color) {
      const el = document.getElementById('views-status');
      el.style.color = color || 'var(--text-muted)';
      el.textContent = msg;
    }

    async function loadSavedViews(selectId) {
      try {
        const resp = await fetch(PIPE + '/api/views');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        savedViews = (await resp.json()).views || [];
      } catch (e) {
        console.warn('[Views] load failed:', e);
        setViewsStatus('Could not load saved views.', '#ff5252');
        return;
      }
      const rsel = document.getElementById('select-replay-view');
      const rkeep = rsel.value;
      rsel.innerHTML = '<option value="">All runs</option>';
      for (const v of savedViews) {
        const o = document.createElement('option');
        o.value = v.id;
        o.textContent = `View: ${v.name}`;
        rsel.appendChild(o);
      }
      rsel.value = savedViews.some(v => v.id === rkeep) ? rkeep : '';

      const sel = document.getElementById('select-saved-view');
      sel.innerHTML = '';
      if (!savedViews.length) {
        sel.innerHTML = '<option value="">No saved views</option>';
        return;
      }
      for (const v of savedViews) {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = v.name;
        opt.title = v.note || '';
        sel.appendChild(opt);
      }
      if (selectId) sel.value = selectId;
    }

    function currentCameraRecord() {
      const cam = viewer.camera;
      const p = cam.position;
      const c = Cesium.Cartographic.fromCartesian(p);
      return {
        x: p.x, y: p.y, z: p.z,
        latitude: Cesium.Math.toDegrees(c.latitude),
        longitude: Cesium.Math.toDegrees(c.longitude),
        height_m: c.height,
        heading_deg: Cesium.Math.toDegrees(cam.heading),
        pitch_deg: Cesium.Math.toDegrees(cam.pitch),
        roll_deg: Cesium.Math.toDegrees(cam.roll),
        fov_deg: Cesium.Math.toDegrees(cam.frustum.fov || 0.785),
        capture_w: CAPTURE_W,
        capture_h: CAPTURE_H
      };
    }

    async function saveCurrentView(overwrite) {
      if (!viewer) return;
      const input = document.getElementById('input-view-name');
      const name = input.value.trim();
      if (!name) { setViewsStatus('Enter a name first.', '#ff5252'); return; }
      const body = { name, camera: currentCameraRecord(), overwrite: !!overwrite, subject: subjectPoint };
      try {
        const resp = await fetch(PIPE + '/api/views', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
        });
        if (resp.status === 409) {
          if (confirm(`A view named "${name}" already exists. Overwrite it with the current camera?`)) {
            return saveCurrentView(true);
          }
          setViewsStatus('Not saved.');
          return;
        }
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const rec = await resp.json();
        input.value = '';
        await loadSavedViews(rec.id);
        setViewsStatus(`Saved: ${rec.name}`, 'var(--accent-cyan)');
        console.log('[Views] saved', rec);
      } catch (e) {
        console.warn('[Views] save failed:', e);
        setViewsStatus('Save failed.', '#ff5252');
      }
    }

    function goToSavedView() {
      if (!viewer) return;
      const id = document.getElementById('select-saved-view').value;
      const v = savedViews.find(s => s.id === id);
      if (!v) { setViewsStatus('Pick a view first.', '#ff5252'); return; }
      const c = v.camera;
      // Exact restore: ECEF position and raw angles, no flight interpolation.
      if (c.fov_deg && viewer.camera.frustum.fov !== undefined) {
        viewer.camera.frustum.fov = Cesium.Math.toRadians(c.fov_deg);
      }
      viewer.camera.setView({
        destination: new Cesium.Cartesian3(c.x, c.y, c.z),
        orientation: {
          heading: Cesium.Math.toRadians(c.heading_deg),
          pitch: Cesium.Math.toRadians(c.pitch_deg),
          roll: Cesium.Math.toRadians(c.roll_deg || 0)
        }
      });
      updateTelemetryHUD();
      onCameraSettle();
      activeSavedView = v;
      if (typeof placeFromCoords === 'function') {
        const at = v.subject || c;
        placeFromCoords(at.latitude, at.longitude);
      }
      if (v.subject) setSubject(v.subject); else clearSubject(true);
      if (typeof saveFraming === 'function') saveFraming(`saved view ${v.name}`);
      setViewsStatus(`At: ${v.name}`, 'var(--accent-cyan)');
      console.log(`[Views] restored ${v.name} (${v.id})`);
    }

    async function deleteSavedView() {
      const id = document.getElementById('select-saved-view').value;
      const v = savedViews.find(s => s.id === id);
      if (!v) return;
      if (!confirm(`Delete saved view "${v.name}"?`)) return;
      try {
        const resp = await fetch(`${PIPE}/api/views/${encodeURIComponent(id)}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        await loadSavedViews();
        setViewsStatus(`Deleted: ${v.name}`);
      } catch (e) {
        console.warn('[Views] delete failed:', e);
        setViewsStatus('Delete failed.', '#ff5252');
      }
    }

    function resetStepperHUD() {
      const stages = ['INGEST_LIGHTING', 'DOMAIN_ENGINE', 'SPATIAL_SCAFFOLD', 'PROMPT_ENGINE', 'VISION_PREPROCESSOR', 'SYNTHESIS_ENGINE', 'ARCHIVER'];
      stages.forEach(s => {
        const row = document.getElementById(`row-${s}`);
        if (row) {
          row.className = 'stage-row pending';
          row.querySelector('.stage-timer').textContent = '--';
          row.querySelector('.stage-status-badge').textContent = 'PENDING';
        }
      });
      document.getElementById('stepperTicker').textContent = 'Booting spatial pipeline...';
    }

    function updateStageHUD(event) {
      const row = document.getElementById(`row-${event.stage}`);
      if (!row) return;

      const timer = row.querySelector('.stage-timer');
      const badge = row.querySelector('.stage-status-badge');
      const ticker = document.getElementById('stepperTicker');

      if (event.state === 'ACTIVATED') {
        row.className = 'stage-row active';
        badge.textContent = 'ACTIVE';
        ticker.textContent = `▶ [${event.label}] ${event.message}`;
      } else if (event.state === 'PROCESSING') {
        ticker.textContent = `⚙ [${event.label}] ${event.message}`;
      } else if (event.state === 'DISPATCHING') {
        ticker.textContent = `▲ [${event.label}] ${event.message}`;
      } else if (event.state === 'STANDBY') {
        row.className = 'stage-row done';
        badge.textContent = 'DONE';
        if (event.duration_ms) timer.textContent = `${(event.duration_ms / 1000.0).toFixed(2)}s`;
        ticker.textContent = `■ [${event.label}] ${event.message}`;
      } else if (event.state === 'FAULT') {
        row.className = 'stage-row fault';
        badge.textContent = 'FAULT';
        ticker.textContent = `✖ [${event.label}] ${event.message}`;
      }
    }

    // Six 90-degree cube faces reprojected to a 2:1 equirectangular panorama.
    // Bases are in local ENU (x=East, y=North, z=Up); right = cross(dir, up).
    const PANO_FACES = [
      { name:'north', heading:0,   pitch:0,   dir:[0,1,0],  up:[0,0,1],  right:[1,0,0] },
      { name:'east',  heading:90,  pitch:0,   dir:[1,0,0],  up:[0,0,1],  right:[0,-1,0] },
      { name:'south', heading:180, pitch:0,   dir:[0,-1,0], up:[0,0,1],  right:[-1,0,0] },
      { name:'west',  heading:270, pitch:0,   dir:[-1,0,0], up:[0,0,1],  right:[0,1,0] },
      { name:'up',    heading:0,   pitch:90,  dir:[0,0,1],  up:[0,-1,0], right:[1,0,0] },
      { name:'down',  heading:0,   pitch:-90, dir:[0,0,-1], up:[0,1,0],  right:[1,0,0] }
    ];

    async function capturePanorama(opts) {
      opts = opts || {};
      const faceSize = opts.faceSize || 1024;
      const outW = opts.width || 2560, outH = Math.round((opts.width || 2560) / 2);
      const settleMs = opts.settleMs || 900, maxWaitMs = opts.maxWaitMs || 8000;
      const scene = viewer.scene, canvas = viewer.canvas;
      const container = document.getElementById('cesiumContainer');
      const saved = {
        position: viewer.camera.position.clone(),
        heading: viewer.camera.heading, pitch: viewer.camera.pitch, roll: viewer.camera.roll,
        fov: scene.camera.frustum.fov, cssW: container.style.width, cssH: container.style.height
      };
      const centerHeading = Cesium.Math.toDegrees(saved.heading);

      function settled() {
        let ok = true;
        if (scene.globe && scene.globe.show) ok = ok && scene.globe.tilesLoaded;
        for (let i = 0; i < scene.primitives.length; i++) {
          const pr = scene.primitives.get(i);
          if (pr instanceof Cesium.Cesium3DTileset && pr.show) ok = ok && pr.tilesLoaded;
        }
        return ok;
      }
      async function waitTiles() {
        const t0 = performance.now();
        while (performance.now() - t0 < maxWaitMs) {
          scene.render();
          await new Promise(r => requestAnimationFrame(r));
          if (settled()) break;
        }
        await new Promise(r => setTimeout(r, settleMs));
        scene.render();
        await new Promise(r => requestAnimationFrame(r));
      }

      container.style.width = faceSize + 'px';
      container.style.height = faceSize + 'px';
      viewer.resize();
      scene.camera.frustum.fov = Cesium.Math.toRadians(90);

      const faces = [];
      try {
        for (const f of PANO_FACES) {
          viewer.camera.setView({
            destination: saved.position,
            orientation: {
              heading: Cesium.Math.toRadians(centerHeading + f.heading),
              pitch: Cesium.Math.toRadians(f.pitch), roll: 0
            }
          });
          await waitTiles();
          const tmp = document.createElement('canvas');
          tmp.width = faceSize; tmp.height = faceSize;
          const c2 = tmp.getContext('2d');
          c2.drawImage(canvas, 0, 0, faceSize, faceSize);
          faces.push(Object.assign({}, f, { img: c2.getImageData(0, 0, faceSize, faceSize) }));
        }
      } finally {
        container.style.width = saved.cssW;
        container.style.height = saved.cssH;
        viewer.resize();
        scene.camera.frustum.fov = saved.fov;
        viewer.camera.setView({
          destination: saved.position,
          orientation: { heading: saved.heading, pitch: saved.pitch, roll: saved.roll }
        });
        scene.render();
      }

      const out = document.createElement('canvas');
      out.width = outW; out.height = outH;
      const octx = out.getContext('2d');
      const oimg = octx.createImageData(outW, outH);
      const O = oimg.data;
      const cH = centerHeading * Math.PI / 180;
      for (let y = 0; y < outH; y++) {
        const el = (0.5 - (y + 0.5) / outH) * Math.PI;
        const ce = Math.cos(el), se = Math.sin(el);
        for (let x = 0; x < outW; x++) {
          const az = cH + ((x + 0.5) / outW - 0.5) * 2 * Math.PI;
          const dE = Math.sin(az) * ce, dN = Math.cos(az) * ce, dU = se;
          let r = 0, g = 0, b = 0;
          for (const f of faces) {
            const a = dE*f.dir[0] + dN*f.dir[1] + dU*f.dir[2];
            if (a <= 1e-6) continue;
            const sx = (dE*f.right[0] + dN*f.right[1] + dU*f.right[2]) / a;
            if (sx < -1 || sx > 1) continue;
            const sy = (dE*f.up[0] + dN*f.up[1] + dU*f.up[2]) / a;
            if (sy < -1 || sy > 1) continue;
            const px = Math.min(faceSize-1, Math.max(0, Math.floor((sx+1)*0.5*faceSize)));
            const py = Math.min(faceSize-1, Math.max(0, Math.floor((1-sy)*0.5*faceSize)));
            const i = (py*faceSize + px) * 4;
            r = f.img.data[i]; g = f.img.data[i+1]; b = f.img.data[i+2];
            break;
          }
          const o = (y*outW + x) * 4;
          O[o]=r; O[o+1]=g; O[o+2]=b; O[o+3]=255;
        }
      }
      octx.putImageData(oimg, 0, 0);
      window.__pano = { dataUrl: out.toDataURL('image/jpeg', 0.92), centerAzimuth_deg: centerHeading };
      return window.__pano.dataUrl;
    }

    // The synthesis API is asked for 16:9. If the seed is a different shape the
    // model must crop it, and it picks a different crop each run. Capturing at a
    // fixed 16:9 removes that decision and makes the seed reproducible across
    // machines and window sizes.
    const CAPTURE_W = 2560, CAPTURE_H = 1440;

    async function captureFixedAspect(quality) {
      const scene = viewer.scene;
      const container = document.getElementById('cesiumContainer');
      const saved = { cssW: container.style.width, cssH: container.style.height };
      let dataUrl = null;
      try {
        container.style.width = CAPTURE_W + 'px';
        container.style.height = CAPTURE_H + 'px';
        viewer.resize();
        const t0 = performance.now();
        while (performance.now() - t0 < 6000) {
          scene.render();
          await new Promise(r => requestAnimationFrame(r));
          let ok = true;
          for (let i = 0; i < scene.primitives.length; i++) {
            const pr = scene.primitives.get(i);
            if (pr instanceof Cesium.Cesium3DTileset && pr.show) ok = ok && pr.tilesLoaded;
          }
          if (ok) break;
        }
        await new Promise(r => setTimeout(r, 400));
        scene.render();
        await new Promise(r => requestAnimationFrame(r));
        dataUrl = viewer.canvas.toDataURL('image/jpeg', quality || 0.9);
        console.log(`[Capture] ${viewer.canvas.width} x ${viewer.canvas.height}`);
      } finally {
        container.style.width = saved.cssW;
        container.style.height = saved.cssH;
        viewer.resize();
        scene.render();
      }
      return dataUrl;
    }

    // Resolve what the camera is looking at: the surface point under the frame-center ray.
    // Returns null rather than guessing when no real surface is hit (sky, or depth unavailable).
    // The ellipsoid is deliberately NOT used as a fallback: on an oblique ray it lands
    // hundreds of metres past the true surface, which is worse than admitting no target.
    // ---------------- Subject point ----------------
    // The building or object a view is about. Captures aim at it instead of the frame centre,
    // so the address, domain analysis and (later) Street View selection follow what you chose.
    let subjectPoint = null;        // { x, y, z, latitude, longitude, height_m }
    let subjectEntity = null;
    let subjectPickMode = false;

    function setSubjectStatus(msg, color) {
      const el = document.getElementById('subject-status');
      el.style.color = color || 'var(--text-muted)';
      el.textContent = msg;
    }

    function describeSubject() {
      if (!subjectPoint) { setSubjectStatus('No subject set: captures aim at the centre of the frame.'); return; }
      const d = Cesium.Cartesian3.distance(viewer.camera.position, new Cesium.Cartesian3(subjectPoint.x, subjectPoint.y, subjectPoint.z));
      setSubjectStatus(`🎯 Subject: ${subjectPoint.latitude.toFixed(6)}, ${subjectPoint.longitude.toFixed(6)} | ${d.toFixed(0)} m from camera`, 'var(--accent-cyan)');
    }

    function setSubject(p) {
      subjectPoint = p;
      if (subjectEntity) { viewer.entities.remove(subjectEntity); subjectEntity = null; }
      subjectEntity = viewer.entities.add({
        position: new Cesium.Cartesian3(p.x, p.y, p.z),
        point: { pixelSize: 12, color: Cesium.Color.fromCssColorString('#00e5ff'), outlineColor: Cesium.Color.BLACK,
                 outlineWidth: 2, disableDepthTestDistance: Number.POSITIVE_INFINITY },
        label: { text: 'SUBJECT', font: '11px monospace', pixelOffset: new Cesium.Cartesian2(0, -18),
                 fillColor: Cesium.Color.WHITE, showBackground: true, disableDepthTestDistance: Number.POSITIVE_INFINITY }
      });
      describeSubject();
    }

    function clearSubject(silent) {
      subjectPoint = null;
      if (subjectEntity) { viewer.entities.remove(subjectEntity); subjectEntity = null; }
      subjectPickMode = false;
      document.getElementById('btn-set-subject').textContent = '🎯 SET SUBJECT';
      if (!silent) describeSubject(); else setSubjectStatus('No subject set: captures aim at the centre of the frame.');
    }

    function toggleSubjectPick() {
      subjectPickMode = !subjectPickMode;
      document.getElementById('btn-set-subject').textContent = subjectPickMode ? '🎯 CLICK THE SUBJECT… (Esc cancels)' : '🎯 SET SUBJECT';
      if (subjectPickMode) setSubjectStatus('Click the building or object this view is about.', '#ffb74d'); else describeSubject();
    }

    function pickSurfaceAt(windowPos) {
      const scene = viewer.scene;
      let pos = null;
      if (scene.pickPositionSupported) {
        try { pos = scene.pickPosition(windowPos); } catch (e) { pos = null; }
      }
      if (!pos && scene.globe && scene.globe.show) {
        const ray = viewer.camera.getPickRay(windowPos);
        if (ray) pos = scene.globe.pick(ray, scene);
      }
      return pos || null;
    }

    function initSubjectPicking() {
      const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      handler.setInputAction(click => {
        if (!subjectPickMode) return;
        const pos = pickSurfaceAt(click.position);
        if (!pos) { setSubjectStatus('No surface there. Click a building, the ground, or an object.', '#ff5252'); return; }
        const c = Cesium.Cartographic.fromCartesian(pos);
        subjectPickMode = false;
        document.getElementById('btn-set-subject').textContent = '🎯 SET SUBJECT';
        setSubject({ x: pos.x, y: pos.y, z: pos.z, latitude: Cesium.Math.toDegrees(c.latitude),
                     longitude: Cesium.Math.toDegrees(c.longitude), height_m: c.height });
        console.log('[Subject] set', subjectPoint);
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
      document.addEventListener('keydown', e => {
        if (subjectPickMode && e.key === 'Escape') { subjectPickMode = false; document.getElementById('btn-set-subject').textContent = '🎯 SET SUBJECT'; describeSubject(); }
      });
      viewer.camera.moveEnd.addEventListener(() => { if (subjectPoint) describeSubject(); });
    }

    // At capture: aim at the subject if it is in frame, otherwise fall back to the frame centre.
    async function resolveCaptureTarget() {
      if (subjectPoint) {
        const p = new Cesium.Cartesian3(subjectPoint.x, subjectPoint.y, subjectPoint.z);
        const toWin = Cesium.SceneTransforms.worldToWindowCoordinates || Cesium.SceneTransforms.wgs84ToWindowCoordinates;
        const win = toWin(viewer.scene, p);
        const canvas = viewer.scene.canvas;
        const toP = Cesium.Cartesian3.subtract(p, viewer.camera.position, new Cesium.Cartesian3());
        const inFront = Cesium.Cartesian3.dot(toP, viewer.camera.direction) > 0;
        const inFrame = win && inFront && win.x >= 0 && win.y >= 0 && win.x <= canvas.clientWidth && win.y <= canvas.clientHeight;
        if (inFrame) {
          const t = {
            latitude: subjectPoint.latitude, longitude: subjectPoint.longitude, height_m: subjectPoint.height_m,
            distance_m: Cesium.Cartesian3.distance(viewer.camera.position, p), method: 'SUBJECT_CLICK'
          };
          console.log(`[Target] SUBJECT_CLICK: ${t.latitude.toFixed(6)}, ${t.longitude.toFixed(6)} @ ${t.distance_m.toFixed(1)} m`);
          return t;
        }
        console.warn('[Target] subject is out of frame; aiming at the frame centre instead');
      }
      return await pickFrameTarget();
    }

    async function pickFrameTarget() {
      const scene = viewer.scene;
      const canvas = scene.canvas;
      const center = new Cesium.Cartesian2(canvas.clientWidth / 2, canvas.clientHeight / 2);
      scene.render();
      await new Promise(r => requestAnimationFrame(r));
      let pos = null, method = null;
      if (scene.pickPositionSupported) {
        try {
          pos = scene.pickPosition(center);
          if (pos) method = 'PICK_POSITION';
        } catch (e) {
          console.warn('[Target] pickPosition failed:', e);
        }
      }
      if (!pos && scene.globe && scene.globe.show) {
        const ray = viewer.camera.getPickRay(center);
        if (ray) {
          pos = scene.globe.pick(ray, scene);
          if (pos) method = 'GLOBE_PICK';
        }
      }
      if (!pos) {
        console.warn('[Target] no surface under frame center; server will fall back to camera position');
        return null;
      }
      const dist = Cesium.Cartesian3.distance(viewer.camera.position, pos);
      if (!Number.isFinite(dist) || dist > 20000) {
        console.warn(`[Target] rejected implausible pick (${dist} m)`);
        return null;
      }
      const c = Cesium.Cartographic.fromCartesian(pos);
      const t = {
        latitude: Cesium.Math.toDegrees(c.latitude),
        longitude: Cesium.Math.toDegrees(c.longitude),
        height_m: c.height,
        distance_m: dist,
        method
      };
      console.log(`[Target] ${method}: ${t.latitude.toFixed(6)}, ${t.longitude.toFixed(6)} @ ${dist.toFixed(1)} m`);
      return t;
    }

    async function captureAndSynthesizeTwin() {
      if (!viewer) return;
      if (!confirmDropEdits('Synthesize')) return;
      if (typeof saveFraming === 'function') saveFraming('capture');
      const atView = cameraMatchesView(activeSavedView) ? activeSavedView : null;
      console.log(atView ? `[Views] capture tagged with view: ${atView.name}` : '[Views] capture not at a saved view (untagged)');
      resetStepperHUD();
      document.getElementById('loadingOverlay').classList.remove('hidden');

      // The subject marker must never appear in the seed image.
      if (subjectEntity) subjectEntity.show = false;
      
      // Fixed 16:9 seed so the model never has to choose a crop.
      // With "Sun and shadows" ticked, capture twice at the same camera and time: without Cesium's shadows
      // (the seed, delighted as usual) and with them (the shadow pass, laid onto the delighted seed server-side).
      const sunShadows = !!document.getElementById('chk-sun-shadows')?.checked;
      let screenshotB64, shadowPassB64 = null;
      if (sunShadows) {
        setSunShadows(false);
        screenshotB64 = await captureFixedAspect(0.92);
        setSunShadows(true);
        shadowPassB64 = await captureFixedAspect(0.92);
        console.log('[Sun] captured a shadowless seed and a shadow pass');
      } else {
        screenshotB64 = await captureFixedAspect(0.9);
      }

      const cart = Cesium.Cartographic.fromCartesian(viewer.camera.position);
      const altInfo = await computeAltitudeAGL(cart);
      const target = await resolveCaptureTarget();
      const isLiveTime = document.getElementById('chk-live-time').checked;

      const marbleMode = currentProvider === 'WORLD_LABS'
        ? document.getElementById('select-marble-input').value : 'text';
      let panoB64 = null;
      if (currentProvider === 'WORLD_LABS' && marbleMode === 'pano') {
        console.log('[Pano] capturing 360 panorama for Marble...');
        try {
          panoB64 = await capturePanorama();
          console.log('[Pano] captured');
        } catch (e) {
          console.error('[Pano] capture failed, falling back to text:', e);
        }
      }

      const payload = {
        screenshot_b64: document.getElementById('select-view-scope').value === 'STANDALONE' ? null : screenshotB64,
        telemetry: {
          latitude: Cesium.Math.toDegrees(cart.latitude),
          longitude: Cesium.Math.toDegrees(cart.longitude),
          altitude_agl: altInfo.agl,
          ground_elevation_m: altInfo.ground_m,
          altitude_method: altInfo.method,
          heading: Cesium.Math.toDegrees(viewer.camera.heading),
          pitch: Cesium.Math.toDegrees(viewer.camera.pitch),
          fov: Cesium.Math.toDegrees(viewer.camera.frustum.fov || 0.785),
          target_latitude: target ? target.latitude : null,
          target_longitude: target ? target.longitude : null,
          target_height_m: target ? target.height_m : null,
          target_distance_m: target ? target.distance_m : null,
          target_method: target ? target.method : null,
          tile_mode: tilesLoaded ? '3D_TILES' : '2D_IMAGERY',
          date: isLiveTime ? null : document.getElementById('input-date').value,
          time_of_day: isLiveTime ? null : parseFloat(document.getElementById('input-time-slider').value),
          timestamp_utc: isLiveTime ? new Date().toISOString() : null,
          lighting_mode: currentLightingMode,
          weather_mode: currentWeatherMode
        },
        pano_b64: panoB64,
        marble_input_mode: panoB64 ? 'pano' : (marbleMode === 'pano' ? 'text' : marbleMode),
        gemini_budget: parseInt(document.getElementById('slider-gemini-budget').value, 10),
        provider: currentProvider,
        target_model: currentProvider === 'WORLD_LABS'
          ? document.getElementById('select-marble-model').value : 'gemini-3.1-flash-image',
        view_scope: document.getElementById('select-view-scope').value,
        disable_recaption: document.getElementById('chk-disable-recaption').checked,
        use_search_grounding: document.getElementById('chk-search-grounding').checked,
        saved_view_id: atView ? atView.id : null,
        saved_view_name: atView ? atView.name : null,
        shadow_pass_b64: document.getElementById('select-view-scope').value === 'STANDALONE' ? null : shadowPassB64
      };

      if (subjectEntity) subjectEntity.show = true;
      await streamPipeline(payload);
    }

    // The run id an archived pipeline result was saved under (the run folder's name).
    function runIdFromResult(data) {
      const p = data && data.run_record && data.run_record.path;
      return p ? String(p).split(/[\\/]/).filter(Boolean).pop() : null;
    }

    // Hand edits in the scene editor that the next action won't use are lost when the list
    // jumps to the new run. Synthesize and Print don't use them; Replay and Make keystone do.
    function confirmDropEdits(action) {
      if (!editedSceneText()) return true;
      return confirm(`The scene text has hand edits (Pro Mode) that ${action} does not use.\n\n` +
        'When it finishes, the new run is selected and its own scene text replaces the editor, so these edits will be lost.\n\nContinue?');
    }

    // Shared by fresh captures and replays: posts the request and drives the stepper HUD.
    // When it finishes, the run it made is selected, so the list never stays on an older run.
    async function streamPipeline(payload) {
      let newRunId = null;

      try {
        const response = await fetch(PIPE + '/api/process_view', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop(); // Keep partial line in buffer

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            let packet;
            try { packet = JSON.parse(trimmed); }
            catch (e) { console.warn('[Pipeline] skipped a malformed line from the server:', trimmed.slice(0, 200)); continue; }

            if (packet.type === 'LIFECYCLE') {
              updateStageHUD(packet);
            } else if (packet.type === 'RESULT') {
              newRunId = runIdFromResult(packet.data);
              displayResults(packet.data);
            } else if (packet.type === 'ERROR') {
              alert('Pipeline Error: ' + packet.message);
            }
          }
        }
      } catch (err) {
        alert('Synthesis Network Error: ' + err.message);
      } finally {
        setTimeout(() => {
          document.getElementById('loadingOverlay').classList.add('hidden');
        }, 600);
        // A new run: select it. A failed run made nothing: stay where you were.
        loadReplayRuns(true, newRunId);
      }
    }

    // ---------------- Replay ----------------
    let replayRuns = [];
    let replayOriginalText = '';
    let keystones = {};   // view_id -> approved keystone record
    let thumbShowsRender = true;

    function setReplayThumb(id) {
      const thumb = document.getElementById('replay-thumb');
      const file = thumbShowsRender ? 'spatial_twin.png' : 'viewport_capture.jpg';
      thumb.src = `${PIPE}/api/runs/${encodeURIComponent(id)}/file/${file}`;
      thumb.title = 'Click to view full screen';
    }

    // ---------------- Street View reference ----------------
    // Images are only ever previewed, fetched through the server and never stored;
    // the run records the pano ID, view settings and the notes you keep.
    let svState = null;   // { pano_id, heading, pitch, fov, date, distance_m, copyright, size, source_url }

    // Frames are fetched at 16:9 to match the Maps view and the Cesium capture. The API's fov is
    // horizontal; a Maps link's "y" value is vertical (verified 2026-10-09 at Abercromby Place).
    const SV_SIZE = '640x360', SV_ASPECT = 16 / 9, SV_SQUARE = '640x640';
    const DEG = Math.PI / 180;
    const r1 = x => Math.round(x * 10) / 10, r2 = x => Math.round(x * 100) / 100;
    function hfovFromMaps(v) { return Math.min(120, 2 * Math.atan(Math.tan(v * DEG / 2) * SV_ASPECT) / DEG); }
    function mapsFromHfov(h, size) { return size === SV_SQUARE ? h : 2 * Math.atan(Math.tan(h * DEG / 2) / SV_ASPECT) / DEG; }
    function lensMm(h) { return 36 / (2 * Math.tan(h * DEG / 2)); }   // across a 36 mm frame, as on the dial

    // A Street View address from the Maps browser bar:
    //   .../@lat,lon,50a,75y,71.15h,88.06t/data=!3m7!1e1!3m5!1s<pano id>!2e0!6s<thumbnail>...
    // y = vertical FOV, h = heading, t = tilt (pitch is t - 90; the thumbnail's own pitch has the
    // opposite sign and is never used). The pano ID runs to the next "!", whatever its length.
    // !2e0 marks Google's own imagery; any other value is treated as a user photosphere.
    function parseMapsUrl(raw) {
      const u = String(raw || '').trim();
      const at = u.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:,[\d.]+a)?,([\d.]+)y,(-?[\d.]+)h(?:,([\d.]+)t)?/);
      const pano = u.match(/!1s([^!?&#\/]+)/);
      if (!at || !pano) return null;
      const kind = (u.match(/!2e(\d+)/) || [])[1];
      const vfov = parseFloat(at[3]);
      const t = at[5] !== undefined ? parseFloat(at[5]) : 90;
      let pid = pano[1];
      try { pid = decodeURIComponent(pid); } catch (e) {}
      return {
        lat: parseFloat(at[1]), lon: parseFloat(at[2]),
        heading: r2(((parseFloat(at[4]) % 360) + 360) % 360), pitch: r2(t - 90),
        maps_fov: vfov, fov: r1(hfovFromMaps(vfov)),
        pano_id: pid, kind: kind === undefined ? null : kind, photosphere: kind !== undefined && kind !== '0'
      };
    }

    function svUpdateFovNote() {
      const el = document.getElementById('sv-fov-note');
      const h = parseFloat(document.getElementById('sv-fov').value);
      if (!el) return;
      if (!Number.isFinite(h)) { el.textContent = ''; return; }
      const size = svState && svState.size;
      el.textContent = size === SV_SQUARE
        ? `Square crop, made before the 16:9 switch: ${r1(h)}° both ways.`
        : `${r1(h)}° across = Maps ${r1(mapsFromHfov(h))}° · about ${Math.round(lensMm(h))} mm`;
    }
    document.getElementById('sv-fov').addEventListener('input', svUpdateFovNote);

    async function svFromUrl() {
      const raw = document.getElementById('sv-url').value;
      const p = parseMapsUrl(raw);
      if (!p) {
        setSvStatus('No Street View position found in that link. Copy the address from the browser bar while Street View is open in Maps.', '#ff5252');
        return;
      }
      const run = selectedReplayRun();
      const subjFor = svSubjectFor(run);
      const subj = subjFor || { lat: p.lat, lon: p.lon };
      setSvStatus(p.photosphere ? 'This link looks like a user photosphere; checking whether the API can serve it...' : 'Reading the pano...');
      let meta;
      try { meta = await svFetchMeta(subj, p.pano_id); }
      catch (e) {
        setSvStatus(p.photosphere
          ? 'This is a user photosphere. The Street View API cannot serve those, so it cannot be a keystone reference; a manual screenshot is the only route.'
          : `Pano ${p.pano_id} could not be read: ${e.message}`, '#ff5252');
        return;
      }
      svState = { ...meta, heading: p.heading, pitch: p.pitch, fov: p.fov, size: SV_SIZE, maps_fov: p.maps_fov, source_url: raw.trim() };
      svFillInputs(); svShowPreview();
      setSvStatus(`From the Maps link: heading ${p.heading}°, pitch ${p.pitch}°, Maps FOV ${p.maps_fov}° (vertical) = ${p.fov}° across.` +
        (p.photosphere ? ' Marked as a photosphere, but the API served it.' : '') +
        (subjFor ? '' : ' No subject point, so the distance is not to a subject.') +
        ' Check the preview against Maps edge to edge.', 'var(--accent-cyan)');
    }
    let svPreRewriteText = null;   // scene text before the last condition rewrite, for UNDO

    function setSvStatus(msg, color) {
      const el = document.getElementById('sv-status');
      el.style.color = color || 'var(--text-muted)';
      el.textContent = msg;
    }

    function svSubjectFor(run) {
      if (!run) return null;
      const view = savedViews.find(v => v.id === run.saved_view_id);
      if (view && view.subject) return { lat: view.subject.latitude, lon: view.subject.longitude, source: 'view subject' };
      if (run.target_latitude !== null && run.target_latitude !== undefined)
        return { lat: run.target_latitude, lon: run.target_longitude, source: "run's target point" };
      return null;
    }

    function svReset() {
      svState = null;
      svPreRewriteText = null;
      document.getElementById('btn-sv-undo').style.display = 'none';
      document.getElementById('sv-preview').style.display = 'none';
      document.getElementById('sv-meta').textContent = '';
      const dimg = document.getElementById('sv-detail-preview'); if (dimg) dimg.style.display = 'none';
      renderFinishReport(null);
      const dnote = document.getElementById('sv-detail-note'); if (dnote) dnote.textContent = '';
      ['sv-pano', 'sv-heading', 'sv-pitch', 'sv-fov', 'sv-url'].forEach(id => document.getElementById(id).value = '');
      svUpdateFovNote();
      const run = selectedReplayRun();
      const subj = svSubjectFor(run);
      document.getElementById('sv-context').textContent = !run ? 'Select a run in the Replay card.'
        : subj ? `Aims at the ${subj.source}: ${subj.lat.toFixed(6)}, ${subj.lon.toFixed(6)}`
        : 'This run has no subject or target point; set a subject on its view first.';
      setSvStatus('');
      // A keystone shows the pano it was actually made with, not the view's latest one.
      // It is shown without being remembered for the view; "use these pano settings" does that.
      const own = run && isKeystoneRun(run) && run.streetview && run.streetview.pano_id ? run.streetview : null;
      if (own) {
        svState = { ...own, size: own.size || SV_SQUARE };   // shown exactly as it was fetched
        svFillInputs(false); svShowPreview();
        setSvStatus(`The pano this keystone was made with${own.used === false ? ' (its fetch failed, so the render did not use it)' : ''}.`, 'var(--accent-cyan)');
        return;
      }
      // The pano is a property of the view, not of one run: bring back the last one set for this view.
      const kept = run && svLoadForView(run.saved_view_id);
      if (kept) {
        const old = !kept.size || kept.size === SV_SQUARE;
        svState = { ...kept, size: SV_SIZE };
        svFillInputs(); svShowPreview();
        setSvStatus(old ? 'Pano restored for this view. It was set before the 16:9 switch: same width, but the 16:9 frame shows less at the top and bottom. Check it, or paste the Maps link again.'
                        : 'Pano restored: the last one set for this view.', old ? '#ffb74d' : 'var(--accent-cyan)');
      }
    }

    // Pano ID and view angles only (never the image), remembered per saved view.
    function svKey(viewId) { return viewId ? `lsa.pano.${viewId}` : null; }
    function svLoadForView(viewId) {
      const k = svKey(viewId); if (!k) return null;
      try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; }
    }
    function svRememberForView() {
      const run = selectedReplayRun();
      const k = svKey(run && run.saved_view_id);
      if (!k || !svState) return;
      try { localStorage.setItem(k, JSON.stringify(svState)); } catch (e) {}
    }

    function svFillInputs(remember) {
      if (remember !== false) svRememberForView();
      document.getElementById('sv-pano').value = svState.pano_id;
      document.getElementById('sv-heading').value = svState.heading;
      document.getElementById('sv-pitch').value = svState.pitch;
      document.getElementById('sv-fov').value = svState.fov;
      document.getElementById('sv-url').value = svState.source_url || '';
      svUpdateFovNote();
    }

    function svShowPreview() {
      const s = svState;
      const img = document.getElementById('sv-preview');
      const size = s.size || SV_SQUARE;
      img.src = `${PIPE}/api/streetview/image?pano=${encodeURIComponent(s.pano_id)}&heading=${s.heading}&pitch=${s.pitch}&fov=${s.fov}&size=${size}`;
      img.style.aspectRatio = size === SV_SQUARE ? '1 / 1' : '16 / 9';
      img.style.display = 'block';
      // Guard: the frame must come back in the shape that was asked for, or the preview lies.
      img.onload = () => {
        const want = size === SV_SQUARE ? 1 : SV_ASPECT, got = img.naturalWidth / Math.max(1, img.naturalHeight);
        if (Math.abs(got - want) > 0.05) setSvStatus(`The server sent a ${img.naturalWidth} x ${img.naturalHeight} frame, not ${size}. The 8000 server is running old code: run start_server.bat again.`, '#ff5252');
      };
      const fovTxt = size === SV_SQUARE ? `fov ${s.fov}° (square, before 16:9)` : `fov ${s.fov}° across (Maps ${r1(mapsFromHfov(s.fov))}°)`;
      document.getElementById('sv-meta').textContent =
        `Pano ${s.date || 'date unknown'} · ${s.distance_m} m from subject · heading ${s.heading}° · pitch ${s.pitch}° · ${fovTxt}` +
        `${s.source_url ? ' · from a Maps link' : ''} · ${s.copyright || '© Google'}`;
      svShowDetail();
    }

    // What MAKE KEYSTONE will actually send (2026-10-17). The full pano view pulled renders toward Street View's camera
    // position, so by default the keystone gets a detail crop: aimed from the pano at the subject point, 45° across.
    function svReferenceMode() { return (document.getElementById('sv-reference') || {}).value || 'detail'; }
    // The subject the detail crop aims at: the same point the preview uses, so what is shown is what is sent.
    function svPayload(run) {
      const subj = svSubjectFor(run);
      return { ...svState, reference: svReferenceMode(), subject_lat: subj ? subj.lat : null, subject_lon: subj ? subj.lon : null };
    }
    function svShowDetail() {
      const img = document.getElementById('sv-detail-preview'), note = document.getElementById('sv-detail-note');
      if (!img || !note) return;
      const subj = svSubjectFor(selectedReplayRun());
      if (!svState || svReferenceMode() !== 'detail') {
        img.style.display = 'none';
        note.textContent = svState ? 'The full view above is what MAKE KEYSTONE sends.' : '';
        return;
      }
      if (!subj) { img.style.display = 'none'; note.textContent = 'No subject point on this view: the full view above will be sent instead.'; return; }
      img.src = `${PIPE}/api/streetview/detail?pano=${encodeURIComponent(svState.pano_id)}&lat=${subj.lat}&lon=${subj.lon}&pitch=${svState.pitch}`;
      img.style.display = 'block';
      note.textContent = `This is what MAKE KEYSTONE sends: aimed at the subject from the pano, 45° across, pitch ${svState.pitch}° (the pitch above).`;
    }
    document.getElementById('sv-reference')?.addEventListener('change', svShowDetail);

    async function svFetchMeta(subj, panoId) {
      const resp = await fetch(PIPE + '/api/streetview/propose', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat: subj.lat, lon: subj.lon, pano_id: panoId || null })
      });
      const d = await resp.json();
      if (!resp.ok) throw new Error(d.detail || `HTTP ${resp.status}`);
      return d;
    }

    async function svPropose() {
      const run = selectedReplayRun();
      const subj = svSubjectFor(run);
      if (!subj) { setSvStatus('Select a run whose view has a subject point.', '#ff5252'); return; }
      setSvStatus('Finding the nearest outdoor pano...');
      try {
        svState = await svFetchMeta(subj, null);
        svFillInputs(); svShowPreview();
        setSvStatus('Check the preview shows the subject. Adjust heading, pitch or field of view, or paste another pano ID, then UPDATE.', 'var(--accent-cyan)');
      } catch (e) { setSvStatus(e.message, '#ff5252'); }
    }

    async function svApplyOverride() {
      const run = selectedReplayRun();
      const subj = svSubjectFor(run);
      if (!subj) { setSvStatus('Select a run whose view has a subject point.', '#ff5252'); return; }
      const pano = document.getElementById('sv-pano').value.trim();
      const num = id => { const v = parseFloat(document.getElementById(id).value); return Number.isFinite(v) ? v : null; };
      try {
        if (!svState || pano !== svState.pano_id) {
          svState = await svFetchMeta(subj, pano || null);   // a new pano: fresh date, distance and aimed heading
          if (num('sv-pitch') !== null) svState.pitch = num('sv-pitch');
          if (num('sv-fov') !== null) svState.fov = num('sv-fov');
        } else {
          if (num('sv-heading') !== null) svState.heading = num('sv-heading');
          if (num('sv-pitch') !== null) svState.pitch = num('sv-pitch');
          if (num('sv-fov') !== null) svState.fov = num('sv-fov');
        }
        const linked = svState.source_url && svState.pano_id === pano;
        svState.size = SV_SIZE;
        if (linked) {
          const p = parseMapsUrl(svState.source_url);
          if (!p || p.heading !== svState.heading || p.pitch !== svState.pitch || p.fov !== svState.fov) { svState.source_url = null; svState.maps_fov = null; }
        } else { svState.source_url = null; svState.maps_fov = null; }
        svFillInputs(); svShowPreview();
        setSvStatus(svState.source_url ? 'Preview updated.' : 'Preview updated. Set by hand: it no longer matches a Maps link.', 'var(--accent-cyan)');
      } catch (e) { setSvStatus(e.message, '#ff5252'); }
    }

    async function svRead() {
      const run = selectedReplayRun();
      if (!run || !svState) { setSvStatus('Propose a pano first.', '#ff5252'); return; }
      const box = document.getElementById('replay-scene-text');
      setSvStatus('Reading the pano against the capture...');
      try {
        const resp = await fetch(PIPE + '/api/streetview/read', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_id: run.id, pano_id: svState.pano_id, heading: svState.heading, pitch: svState.pitch,
                                 fov: svState.fov, date: svState.date, scene_text: box.value })
        });
        const d = await resp.json();
        if (!resp.ok) throw new Error(d.detail || `HTTP ${resp.status}`);
        box.value = `${box.value.trim()}\n\nStreet View reference notes (${svState.date || 'undated'}): ${d.notes}`;
        box.scrollTop = box.scrollHeight;
        setSvStatus('Notes added to the scene text. Review and edit them before MAKE KEYSTONE.', 'var(--accent-cyan)');
      } catch (e) { setSvStatus(e.message, '#ff5252'); }
    }

    // Finishing pass: the scene text comes back whole, with only its surface condition rewritten from the pano.
    async function svRewrite() {
      const run = selectedReplayRun();
      if (!run || !svState) { setSvStatus('Propose a pano first.', '#ff5252'); return; }
      const box = document.getElementById('replay-scene-text');
      const before = box.value;
      setSvStatus('Running the finishing pass against the pano...');
      try {
        const resp = await fetch(PIPE + '/api/streetview/rewrite', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_id: run.id, pano_id: svState.pano_id, heading: svState.heading, pitch: svState.pitch,
                                 fov: svState.fov, date: svState.date, scene_text: before })
        });
        const d = await resp.json();
        if (!resp.ok) throw new Error(d.detail || `HTTP ${resp.status}`);
        if (!d.changed) { setSvStatus('The pano matched the scene text; nothing was changed.', 'var(--accent-cyan)'); renderFinishReport(d); return; }
        svPreRewriteText = before;
        if (lsaJoin) lsaJoin.finishing_after = true;   // A/B: only the B text has had the finishing pass
        box.value = d.scene_text; if (typeof updateSceneState === 'function') updateSceneState();
        box.scrollTop = 0;
        document.getElementById('btn-sv-undo').style.display = '';
        renderFinishReport(d);
        setSvStatus(`Finishing pass from pano ${d.pano_id} (${d.date || 'undated'}): ${before.length} → ${d.scene_text.length} chars.` +
          (d.removed && d.removed.length ? ` It REMOVED structure: ${d.removed.join(', ')}. Check the report below.` : '') +
          ' Review it before MAKE KEYSTONE; UNDO restores the previous text.', d.removed && d.removed.length ? '#ffb74d' : 'var(--accent-cyan)');
      } catch (e) { setSvStatus(e.message, '#ff5252'); }
    }

    // Structural terms a pass took out of the scene text (found by comparing the texts on the server).
    function removedHtml(removed, who) {
      if (!removed || !removed.length) return `<div class="lsa-added-note">Structure removed: none.</div>`;
      return `<div class="lsa-added-head" style="color: var(--rust);">Removed by ${escHtml(who)}: check</div>` +
        `<div class="lsa-added-note">These were in the scene text before and are gone now: <b>${removed.map(escHtml).join(', ')}</b>. ` +
        `Put back what is real (UNDO, or edit by hand).</div>`;
    }

    // Finishing pass report: what it added, where the pano seems to disagree with the scene text, and what it removed.
    function renderFinishReport(d) {
      const el = document.getElementById('sv-finish-report');
      if (!el) return;
      if (!d) { el.hidden = true; el.innerHTML = ''; return; }
      const added = d.added || [], conflicts = d.conflicts || [];
      el.innerHTML = removedHtml(d.removed, 'the finishing pass') +
        `<div class="lsa-added-head">Added from the pano</div>` +
        (added.length ? added.map(a => `<div class="lsa-added-text">"${escHtml(a.phrase)}" <span class="lsa-added-note">${escHtml(a.note || '')}</span></div>`).join('')
                      : '<div class="lsa-added-note">Nothing structural added.</div>') +
        `<div class="lsa-added-head">Where the pano seems to disagree (not applied)</div>` +
        (conflicts.length ? conflicts.map(c => `<div class="lsa-added-text">${escHtml(c)}</div>`).join('') +
          '<div class="lsa-added-note">The scene text was kept. If the pano is right, edit the text by hand (and your Scene layout).</div>'
                          : '<div class="lsa-added-note">No disagreements reported.</div>');
      el.hidden = false;
    }

    function svUndoRewrite() {
      if (svPreRewriteText === null) return;
      document.getElementById('replay-scene-text').value = svPreRewriteText; if (typeof updateSceneState === 'function') updateSceneState();
      svPreRewriteText = null;
      document.getElementById('btn-sv-undo').style.display = 'none';
      renderFinishReport(null);
      setSvStatus('Scene text restored to before the finishing pass.');
    }

    // Make a keystone's recorded pano the view's current one, for the next keystone.
    function svUseKeystonePano(run) {
      const sv = run && run.streetview;
      if (!sv || !sv.pano_id) return;
      const old = !sv.size || sv.size === SV_SQUARE;
      svState = { pano_id: sv.pano_id, heading: sv.heading, pitch: sv.pitch, fov: sv.fov,
                  date: sv.date, distance_m: sv.distance_m, copyright: sv.copyright, size: SV_SIZE,
                  source_url: old ? null : (sv.source_url || null) };
      svFillInputs(); svShowPreview();
      setSvStatus(old ? 'These angles are now the view\'s current pano. They were a square crop: same width, but the 16:9 frame shows less at the top and bottom. Check it before the next keystone.'
                      : 'These pano settings are now the view\'s current pano and will be used by the next keystone.', old ? '#ffb74d' : 'var(--accent-cyan)');
    }

    // ---------------- Weft pass (2026-10-15, revised 2026-10-16; named the weft pass 2026-10-17, formerly the LSA pass) ----------------
    // Weaves an LSA Studio run into the selected pipeline run's scene text. The LSA run's brief (place, standpoint,
    // looking at, scene layout) goes with it as the director's layout: its structure is confirmed, and its street
    // names are turned into position words. Every structural addition comes back with a status (confirmed or
    // proposed) for Don to keep or remove. LSA runs live on this page's own server (8001); the weave runs on 8000.
    let lsaRuns = [];
    let lsaJoin = null;   // { run_id, label, instruction, text_before, text_after, ecology, added_structure, species_to_verify, set_aside, not_added, finishing_after, director_layout_used }
    const lsaDetailCache = {};

    function setLsaStatus(msg, color) {
      const el = document.getElementById('lsa-join-status');
      if (!el) return;
      el.style.color = color || 'var(--text-muted)';
      el.textContent = msg;
    }

    function lsaReset() {
      lsaJoin = null;
      const undo = document.getElementById('btn-lsa-undo');
      if (undo) undo.style.display = 'none';
      const notes = document.getElementById('lsa-join-notes');
      if (notes) notes.hidden = true;
      const added = document.getElementById('lsa-join-added');
      if (added) { added.hidden = true; added.innerHTML = ''; }
      setLsaStatus('');
    }

    function fmtLsaRun(r) {
      const when = r.created ? String(r.created).slice(0, 16).replace('T', ' ') : r.run_id;
      return `${when} · ${r.label || r.place || r.run_id}${r.instruction ? ' (' + String(r.instruction).replace(/\.md$/, '') + ')' : ''}` +
        (r.has_image ? '' : ' · no image');
    }

    // A run is usable if it has an analysis. Older 8001 servers don't report that, so fall back to "no error".
    function lsaUsable(r) { return r.has_analysis !== undefined ? !!r.has_analysis : !r.error; }

    // The newest LSA run stamped with the selected run's view is chosen by default; any other can be picked by hand.
    async function loadLsaRuns() {
      const sel = document.getElementById('lsa-join-run');
      if (!sel) return;
      try { const r = await fetch('/api/runs'); lsaRuns = r.ok ? await r.json() : []; } catch (e) { lsaRuns = []; }
      lsaRuns = (Array.isArray(lsaRuns) ? lsaRuns : []).filter(lsaUsable);
      const run = selectedReplayRun();
      const viewId = run ? run.saved_view_id : null;
      const mine = lsaRuns.filter(r => viewId && r.saved_view_id === viewId);
      const rest = lsaRuns.filter(r => !mine.includes(r));
      const opt = r => `<option value="${escHtml(r.run_id)}" title="${escHtml(r.subject || '')}">${escHtml(fmtLsaRun(r))}</option>`;
      if (!lsaRuns.length) { sel.innerHTML = '<option value="">No LSA runs yet</option>'; lsaPreview(); return; }
      sel.innerHTML = '<option value="">Choose an LSA run</option>' +
        (mine.length ? `<optgroup label="Made at this view">${mine.map(opt).join('')}</optgroup>` : '') +
        `<optgroup label="${mine.length ? 'Other LSA runs' : 'LSA runs (none made at this view)'}">${rest.map(opt).join('')}</optgroup>`;
      sel.value = mine.length ? mine[0].run_id : '';
      if (run && !lsaJoin) setLsaStatus(mine.length ? 'The newest LSA run made at this view is selected. Check the preview below.'
        : 'No LSA run is stamped with this view yet: pick one by hand and check the preview.');
      lsaPreview();
    }

    async function lsaDetail(id) {
      if (lsaDetailCache[id]) return lsaDetailCache[id];
      const r = await fetch('/api/runs/' + encodeURIComponent(id));
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return (lsaDetailCache[id] = await r.json());
    }

    // The brief in Don's words, sent with the analysis: structure in it is confirmed.
    function lsaDirectorLayout(shot) {
      shot = shot || {};
      const lines = [
        ['Place', shot.place], ['Standpoint', shot.standpoint], ['Looking at', shot.subject], ['Scene layout', shot.layout],
      ].filter(([, v]) => v && String(v).trim()).map(([k, v]) => `${k}: ${String(v).trim()}`);
      return lines.join('\n');
    }

    // Under the dropdown: the chosen run's image, when it was made, its view stamp and the start of its layout,
    // so the right run is picked before the pass.
    async function lsaPreview() {
      const box = document.getElementById('lsa-join-preview');
      if (!box) return;
      const id = (document.getElementById('lsa-join-run') || {}).value;
      if (!id) { box.hidden = true; return; }
      const thumb = document.getElementById('lsa-join-thumb');
      const brief = document.getElementById('lsa-join-brief');
      box.hidden = false;
      brief.textContent = 'Loading...';
      thumb.style.display = 'none';
      let d;
      try { d = await lsaDetail(id); } catch (e) { brief.textContent = 'Could not read this LSA run: ' + e.message; return; }
      if ((document.getElementById('lsa-join-run') || {}).value !== id) return;   // the pick moved on meanwhile
      const s = d.settings || {}, shot = d.shot || {};
      if (d.image) {
        thumb.src = d.image;
        thumb.style.display = 'block';
        thumb.title = 'Click to open the full image in a new tab';
        thumb.onclick = () => window.open(d.image, '_blank');
      }
      const made = s.created ? new Date(s.created).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
      const stamp = s.saved_view_name ? `made at view "${s.saved_view_name}"` : 'not stamped with a view';
      const layout = (shot.layout || '').trim();
      brief.textContent = `${s.label || shot.place || id} · ${made} · ${s.instruction || ''} · ${stamp}\n` +
        (shot.subject ? `Looking at: ${shot.subject}\n` : '') +
        (layout ? `Scene layout: ${layout.length > 260 ? layout.slice(0, 260) + '...' : layout}`
                : 'No scene layout in this run: only the analysis will be woven in, with no confirmed structure.');
    }
    document.getElementById('lsa-join-run')?.addEventListener('change', lsaPreview);

    async function lsaWeave() {
      const run = selectedReplayRun();
      const id = document.getElementById('lsa-join-run').value;
      if (!run) { setLsaStatus('Select a pipeline run first.', '#ff5252'); return; }
      if (!id) { setLsaStatus('Choose an LSA run.', '#ff5252'); return; }
      if (lsaJoin && !confirm('The scene text already has a weft pass. Run it again on top?\n\n(UNDO first to start from the text before the pass.)')) return;
      const box = document.getElementById('replay-scene-text');
      const before = box.value;
      setLsaStatus('Reading the LSA run...');
      let lsa;
      try { lsa = await lsaDetail(id); } catch (e) { setLsaStatus('Could not read that LSA run: ' + e.message, '#ff5252'); return; }
      if (!(lsa.analysis || '').trim()) { setLsaStatus('That LSA run has no analysis.', '#ff5252'); return; }
      const layout = lsaDirectorLayout(lsa.shot);
      setLsaStatus('Weaving the analysis and your layout into the scene text (about a minute)...', 'var(--accent-cyan)');
      try {
        const resp = await fetch(PIPE + '/api/lsa/weave', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_id: run.id, scene_text: before, analysis: lsa.analysis, lsa_run_id: id, director_layout: layout || null })
        });
        const d = await resp.json();
        if (!resp.ok) throw new Error(d.detail || `HTTP ${resp.status}`);
        if ((selectedReplayRun() || {}).id !== run.id) { setLsaStatus('The selected run changed while the pass ran; nothing was changed.', '#ffb74d'); return; }
        const s = lsa.settings || {};
        lsaJoin = { run_id: id, label: s.label || id, instruction: s.instruction || null,
                    text_before: (lsaJoin ? lsaJoin.text_before : before), text_after: d.scene_text,
                    ecology: d.ecology || '', added_structure: (d.added_structure || []).map(a => ({ ...a, decision: null })), removed: d.removed || [],
                    species_to_verify: d.species_to_verify || [],
                    set_aside: d.set_aside || '', not_added: d.not_added || '', finishing_after: false,
                    director_layout_used: !!layout };
        box.value = d.scene_text;
        if (typeof updateSceneState === 'function') updateSceneState();
        document.getElementById('btn-lsa-undo').style.display = '';
        const notes = [];
        if (lsaJoin.species_to_verify.length) notes.push('Species to verify: ' + lsaJoin.species_to_verify.join(', '));
        if (lsaJoin.not_added) notes.push('Structure not added: ' + lsaJoin.not_added);
        if (lsaJoin.set_aside) notes.push('Light, weather and season set aside (kept with the run): ' + lsaJoin.set_aside);
        document.getElementById('lsa-join-notes-text').textContent = notes.join('\n\n');
        document.getElementById('lsa-join-notes').hidden = !notes.length;
        renderLsaAdded();
        const added = lsaJoin.added_structure;
        const nProp = added.filter(a => a.status === 'proposed').length;
        setLsaStatus(`Weft pass from ${lsaJoin.label}: ${before.length} → ${d.scene_text.length} chars.` +
          (layout ? '' : ' No scene layout was sent (the LSA run has none).') +
          (added.length ? ` Structure added: ${added.length - nProp} confirmed, ${nProp} proposed (listed below).` : ' No structure added.') +
          (d.warnings && d.warnings.length ? ` Check these words in the text: ${d.warnings.join(', ')}.` : '') +
          ' Review it in the editor before making a keystone; UNDO restores the previous text.',
          d.warnings && d.warnings.length ? '#ffb74d' : 'var(--accent-cyan)');
      } catch (e) { setLsaStatus(e.message, '#ff5252'); }
    }

    // The added-structure list: each item with its status, and KEEP or REMOVE. REMOVE takes the phrase out of the
    // editor text; KEEP just records the decision. Decisions go with the run (lsa_join.added_structure).
    function renderLsaAdded() {
      const el = document.getElementById('lsa-join-added');
      if (!el) return;
      if (!lsaJoin) { el.hidden = true; el.innerHTML = ''; return; }
      const items = lsaJoin.added_structure || [];
      const removed = lsaJoin.removed || [];
      const order = { proposed: 0, confirmed: 1 };
      const rows = items.map((a, i) => ({ a, i })).sort((x, y) => order[x.a.status] - order[y.a.status]);
      // Always shown after a pass (2026-10-18), so "nothing added" never looks like "not working".
      el.innerHTML = removedHtml(removed, 'the weft pass') +
        `<div class="lsa-added-head">Added structure: check</div>` +
        (rows.length ? '' : '<div class="lsa-added-note">No structure added.</div>') + rows.map(({ a, i }) => {
        const tag = a.status === 'confirmed' ? 'Confirmed' : 'Proposed';
        const src = { layout: 'from your layout', analysis: 'from the LSA', capture: 'seen in the capture' }[a.source] || a.source;
        const state = a.decision === 'removed' ? '<span class="lsa-added-done">removed</span>'
          : a.decision === 'kept' ? '<span class="lsa-added-done">kept</span>'
          : `<button class="lsa-added-btn" data-i="${i}" data-act="keep">KEEP</button>` +
            `<button class="lsa-added-btn" data-i="${i}" data-act="remove"${a.found ? '' : ' disabled title="Not found word for word in the text: edit it by hand"'}>REMOVE</button>`;
        return `<div class="lsa-added-row ${a.status}${a.decision ? ' decided' : ''}">` +
          `<span class="lsa-added-tag ${a.status}">${tag}</span>` +
          `<span class="lsa-added-text">"${escHtml(a.phrase)}" <span class="lsa-added-note">${escHtml(src)}${a.note ? ': ' + escHtml(a.note) : ''}</span></span>` +
          `<span class="lsa-added-acts">${state}</span></div>`;
      }).join('');
      el.hidden = false;
      el.querySelectorAll('.lsa-added-btn').forEach(b => b.addEventListener('click', () => lsaDecide(+b.dataset.i, b.dataset.act)));
    }

    function lsaDecide(i, act) {
      const a = lsaJoin && lsaJoin.added_structure[i];
      if (!a) return;
      if (act === 'remove') {
        const box = document.getElementById('replay-scene-text');
        if (!box.value.includes(a.phrase)) { setLsaStatus(`"${a.phrase}" is no longer in the text word for word: edit it by hand.`, '#ffb74d'); return; }
        box.value = box.value.replace(a.phrase, '')
          .replace(/\s*\b(and|with|or)\s*([,;.])/g, '$2')   // a dangling join word
          .replace(/\s+([,;.])/g, '$1')            // space before punctuation
          .replace(/([,;])\s*([,;.])/g, '$2')      // doubled punctuation
          .replace(/[ \t]{2,}/g, ' ')
          .replace(/^\s*[,;]\s*/gm, '');
        lsaJoin.text_after = box.value;   // a removal from the list is part of the pass, not a hand edit
        if (typeof updateSceneState === 'function') updateSceneState();
        setLsaStatus(`Removed "${a.phrase}". Read the sentence it was in: the join may need a word.`, 'var(--accent-cyan)');
      }
      a.decision = act === 'remove' ? 'removed' : 'kept';
      renderLsaAdded();
    }

    function lsaUndo() {
      if (!lsaJoin) return;
      document.getElementById('replay-scene-text').value = lsaJoin.text_before;
      if (typeof updateSceneState === 'function') updateSceneState();
      lsaReset();
      setLsaStatus('Scene text restored to before the weft pass.');
    }

    // What the server records with a run made from the woven text. Null when there is no pass, or it was undone.
    function lsaJoinPayload() {
      if (!lsaJoin) return null;
      const text = document.getElementById('replay-scene-text').value.trim();
      if (text === lsaJoin.text_before.trim()) return null;
      return { run_id: lsaJoin.run_id, label: lsaJoin.label, instruction: lsaJoin.instruction, ecology: lsaJoin.ecology,
               added_structure: lsaJoin.added_structure, removed: lsaJoin.removed || [], species_to_verify: lsaJoin.species_to_verify,
               set_aside: lsaJoin.set_aside, not_added: lsaJoin.not_added, director_layout_used: lsaJoin.director_layout_used,
               hand_edited_after: text !== lsaJoin.text_after.trim(), finishing_after: !!lsaJoin.finishing_after };
    }

    // A/B: two keystone candidates from the same run, same seed, same pano. A = the text before the LSA pass,
    // B = the text now (after it). Labelled as a pair, so the comparison can't be crossed.
    async function makeKeystoneAB() {
      const run = selectedReplayRun();
      if (!run) { setReplayStatus('Pick a run first.', '#ff5252'); return; }
      if (!run.saved_view_id) { setReplayStatus('Keystones need a run tagged with a saved view.', '#ff5252'); return; }
      if (!lsaJoin) { setReplayStatus('Run the weft pass (ADD LSA SURFACES) first: A is the scene text before it, B the text after it.', '#ff5252'); return; }
      const textA = lsaJoin.text_before.trim();
      const textB = document.getElementById('replay-scene-text').value.trim();
      if (!textB || textA === textB) { setReplayStatus('The two texts are the same: nothing to compare.', '#ff5252'); return; }
      let seed = readSeed('replay-seed');
      if (seed === null) seed = Math.floor(Math.random() * 2147483646);
      const useSv = !!(svState && document.getElementById('chk-sv-keystone').checked);
      const join = lsaJoinPayload();
      const warn = [];
      if (lsaJoin.finishing_after) warn.push('The finishing pass ran after the weft pass, so only B has had it. For a fair test, UNDO, run the finishing pass first, then the weft pass.');
      if (join && join.hand_edited_after) warn.push('B has hand edits made after the weft pass.');
      if (!confirm(`Make two keystone candidates from this run, both with seed ${seed} and ${useSv ? 'the same Street View pano' : 'no Street View reference'}:\n\n` +
        `A: the scene text before the weft pass (${textA.length} chars)\nB: the scene text after it (${textB.length} chars)\n\n` +
        (warn.length ? 'NOTE: ' + warn.join(' ') + '\n\n' : '') + 'That is two renders. Continue?')) return;
      const pair = 'ab_' + Date.now().toString(36);
      const build = (text, arm) => {
        const p = buildReplayPayload(run, text === replayOriginalText.trim() ? null : text);
        p.mode = 'KEYSTONE';
        p.seed = seed;
        if (useSv) p.streetview = svPayload(run);
        p.ab = { pair_id: pair, arm, seed, lsa_run_id: lsaJoin.run_id };
        return p;
      };
      const pA = build(textA, 'A');
      const pB = build(textB, 'B');
      pB.lsa_join = join;
      console.log(`[A/B] ${pair} from ${run.id}, seed ${seed}`);
      for (const p of [pA, pB]) {
        resetStepperHUD();
        document.getElementById('loadingOverlay').classList.remove('hidden');
        await streamPipeline(p);   // each finished arm is selected as it lands; B is selected at the end
      }
      setReplayStatus(`A/B pair finished (seed ${seed}). Checking both arms' framing against the capture...`, 'var(--accent-cyan)');
      const arms = replayRuns.filter(r => r.ab && r.ab.pair_id === pair);
      const res = {};
      for (const r of arms) { try { res[r.ab.arm] = await fetchAlignment(r.id); } catch (e) { res[r.ab.arm] = null; } }
      const line = arm => res[arm] ? `${arm} ${res[arm].verdict === 'aligned' ? 'held' : res[arm].verdict}${res[arm].verdict === 'aligned' ? '' : ' (' + res[arm].summary + ')'}` : `${arm} not measured`;
      const bothHeld = ['A', 'B'].every(a => res[a] && res[a].verdict === 'aligned');
      setReplayStatus(`A/B pair finished (seed ${seed}). Framing: ${line('A')}; ${line('B')}. ` +
        (bothHeld ? 'Both held: the surfaces can be compared.' : 'Not a fair comparison while an arm has moved: render that arm again (another seed), or realign it.'),
        bothHeld ? 'var(--accent-cyan)' : '#ffb74d');
      const sel = selectedReplayRun();
      if (sel) renderRunFamily(sel);
    }

    // ---------------- Series ----------------
    let seriesExplicitDates = null;
    let seriesPollTimer = null;
    let lastSeries = null;

    function setSeriesStatus(msg, color) {
      const el = document.getElementById('series-status');
      el.style.color = color || 'var(--text-muted)';
      el.textContent = msg;
    }

    function clearSeriesExplicit() {
      seriesExplicitDates = null;
      document.getElementById('series-dates-note').textContent = '';
    }

    function updateSeriesTimeUI() {
      const on = document.getElementById('series-time-range').checked;
      ['series-time-start', 'series-time-end', 'series-time-step'].forEach(id => document.getElementById(id).disabled = !on);
    }

    // Astronomical seasons (approximate: the true dates shift by a day between years).
    function seriesPreset(name) {
      const viewId = keystoneContextViewId();
      const view = savedViews.find(v => v.id === viewId);
      const south = view && view.camera && view.camera.latitude < 0;
      const panelYear = parseInt((document.getElementById('input-date').value || '').slice(0, 4), 10);
      const y = Number.isFinite(panelYear) ? panelYear : new Date().getFullYear();
      const ranges = {
        springN: [`${y}-03-20`, `${y}-06-20`], summerN: [`${y}-06-21`, `${y}-09-22`],
        autumnN: [`${y}-09-23`, `${y}-12-20`], winterN: [`${y}-12-21`, `${y + 1}-03-19`]
      };
      const flip = { spring: 'autumnN', summer: 'winterN', autumn: 'springN', winter: 'summerN' };
      if (name === 'solstices') {
        seriesExplicitDates = [`${y}-03-20`, `${y}-06-21`, `${y}-09-23`, `${y}-12-21`];
        document.getElementById('series-dates-note').textContent = `Fixed dates: ${seriesExplicitDates.join(', ')}`;
        return;
      }
      const r = ranges[south ? flip[name] : `${name}N`];
      document.getElementById('series-start').value = r[0];
      document.getElementById('series-end').value = r[1];
      clearSeriesExplicit();
      document.getElementById('series-dates-note').textContent = `${name[0].toUpperCase() + name.slice(1)} ${south ? '(southern hemisphere)' : ''}: ${r[0]} to ${r[1]}`;
    }

    function seriesSpec(kind) {
      const range = document.getElementById('series-time-range').checked;
      const spec = {
        view_id: keystoneContextViewId(),
        kind,
        step: document.getElementById('series-step').value,
        time_mode: range ? 'range' : 'fixed',
        time_fixed: parseFloat(document.getElementById('input-time-slider').value),
        time_start: parseFloat(document.getElementById('series-time-start').value),
        time_end: parseFloat(document.getElementById('series-time-end').value),
        time_step_hours: parseFloat(document.getElementById('series-time-step').value),
        weather_mode: currentWeatherMode,
        lighting_mode: currentLightingMode,
        gemini_budget: parseInt(document.getElementById('slider-gemini-budget').value, 10),
        target_model: 'gemini-3.1-flash-image',
        disable_recaption: document.getElementById('chk-disable-recaption').checked
      };
      spec.seed = readSeed('series-seed');
      spec.composite = document.getElementById('chk-series-composite').checked;
      if (seriesExplicitDates) spec.dates = seriesExplicitDates;
      else { spec.start_date = document.getElementById('series-start').value; spec.end_date = document.getElementById('series-end').value; }
      return spec;
    }

    function fmtFrameTime(t) { return (t === null || t === undefined) ? '' : ` ${fmtClock(t)}`; }

    async function startSeries(kind) {
      const viewId = keystoneContextViewId();
      if (!viewId || !keystones[viewId]) { setSeriesStatus('This view has no approved keystone yet.', '#ff5252'); return; }
      if (kind === 'prints' && currentWeatherMode === 'AUTO') {
        setSeriesStatus('Pick an explicit weather preset: live weather only applies to today.', '#ff5252');
        return;
      }
      const spec = seriesSpec(kind);
      let plan;
      try {
        const resp = await fetch(PIPE + '/api/series/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(spec) });
        plan = await resp.json();
        if (!resp.ok) throw new Error(plan.detail || `HTTP ${resp.status}`);
      } catch (e) { setSeriesStatus(e.message, '#ff5252'); return; }
      const first = plan.first[0], last = plan.last[0];
      const what = kind === 'phenology' ? 'phenology entries (text only, no renders)' : 'prints';
      const msg = `${plan.count} ${what}: ${plan.dates} date(s) x ${plan.times} time(s).\n` +
        `First: ${first.date}${fmtFrameTime(first.time)}   Last: ${last.date}${fmtFrameTime(last.time)}\n` +
        (kind === 'prints' ? `Weather: ${currentWeatherMode}\nSeed: ${spec.seed !== null ? spec.seed : 'random, the same for every frame'}\n` : '') +
        `Rough estimate: ${plan.estimate_minutes} min.\n\nStart?`;
      if (!confirm(msg)) return;
      if (plan.needs_confirm) {
        if (!confirm(`This is a large series: ${plan.count} frames. Are you sure?`)) return;
        spec.confirm_large = true;
      }
      try {
        const resp = await fetch(PIPE + '/api/series', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(spec) });
        const m = await resp.json();
        if (!resp.ok) throw new Error(m.detail || `HTTP ${resp.status}`);
        lastSeries = m;
        setSeriesStatus(`Started ${m.frames.length} frame(s)...`, 'var(--accent-cyan)');
        pollSeries();
      } catch (e) { setSeriesStatus(e.message, '#ff5252'); }
    }

    async function pollSeries() {
      clearTimeout(seriesPollTimer);
      let a;
      try { a = await (await fetch(PIPE + '/api/series/active')).json(); } catch (e) { return; }
      const m = a.series;
      document.getElementById('btn-series-cancel').style.display = a.running ? 'block' : 'none';
      if (!m) return;
      lastSeries = m;
      const n = m.frames.length;
      const done = m.frames.filter(f => f.status === 'done').length;
      const failed = m.frames.filter(f => f.status === 'failed').length;
      const cur = m.frames.find(f => f.status === 'running');
      const kind = m.kind === 'phenology' ? 'Phenology preview' : 'Series';
      if (a.running) {
        setSeriesStatus(`${kind}: ${done}/${n} done${failed ? `, ${failed} failed` : ''}${cur ? ` | now: ${cur.date}${fmtFrameTime(cur.time)}` : ''}`, 'var(--accent-cyan)');
        seriesPollTimer = setTimeout(pollSeries, 3000);
      } else {
        setSeriesStatus(`${kind} ${m.status.replace(/_/g, ' ')}: ${done}/${n} done${failed ? `, ${failed} failed` : ''}`, failed ? '#ffb74d' : 'var(--text-muted)');
        loadReplayRuns(true);
      }
      document.getElementById('btn-series-rerun').style.display = (!a.running && (failed || m.frames.some(f => f.status === 'pending'))) ? 'block' : 'none';
      document.getElementById('btn-series-pheno').style.display = (m.kind === 'phenology' || done) ? 'block' : 'none';
      if (!a.running && m.kind === 'phenology' && m.status === 'done' && !m._shown) {
        m._shown = true;
        showPhenologyPanel(m);
      }
    }

    async function cancelSeries() {
      if (!lastSeries) return;
      if (!confirm('Cancel the series? It stops after the frame in progress.')) return;
      await fetch(`${PIPE}/api/series/${encodeURIComponent(lastSeries.id)}/cancel`, { method: 'POST' });
      setSeriesStatus('Cancelling after the current frame...', '#ffb74d');
    }

    async function rerunFailedFrames() {
      if (!lastSeries) return;
      const resp = await fetch(`${PIPE}/api/series/${encodeURIComponent(lastSeries.id)}/rerun_failed`, { method: 'POST' });
      const d = await resp.json();
      if (!resp.ok) { setSeriesStatus(d.detail || 'Rerun failed.', '#ff5252'); return; }
      setSeriesStatus(`Rerunning frame(s) ${d.rerunning.join(', ')}...`, 'var(--accent-cyan)');
      pollSeries();
    }

    // Side-by-side phenology text for every date in a series (preview or prints).
    function showPhenologyPanel(m) {
      if (!m) return;
      const rows = m.frames.map(f => {
        const txt = (f.phenology || (f.status === 'failed' ? `FAILED: ${f.error || ''}` : '(pending)'))
          .replace(/&/g, '&amp;').replace(/</g, '&lt;');
        return `<tr><td style="padding: 6px 10px; white-space: nowrap; vertical-align: top; color: var(--accent-cyan);">${f.date}${fmtFrameTime(f.time)}</td>` +
               `<td style="padding: 6px 10px; vertical-align: top;">${txt}</td></tr>`;
      }).join('');
      const esc = t => String(t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
      let calHtml = '';
      const cal = m.calendar;
      if (cal && cal.species) {
        const cols = [['budburst', 'Bud break'], ['full_leaf', 'Full leaf'], ['colour_onset', 'Colour onset'], ['peak_colour', 'Peak colour'], ['half_fall', 'Half fallen'], ['bare', 'Bare']];
        const head = '<tr><th style="padding: 5px 8px; text-align: left;">Plant</th>' + cols.map(c => `<th style="padding: 5px 8px; text-align: left;">${c[1]}</th>`).join('') + '</tr>';
        const body = cal.species.map(sp => `<tr><td style="padding: 5px 8px; font-style: italic;">${esc(sp.name)}</td>` +
          (sp.habit === 'evergreen'
            ? `<td colspan="6" style="padding: 5px 8px; color: var(--text-muted);">evergreen: ${esc(sp.evergreen_look)}</td>`
            : cols.map(c => `<td style="padding: 5px 8px;">${esc((sp.milestones || {})[c[0]])}</td>`).join('')) + '</tr>').join('');
        calHtml = `<div style="color: var(--text-muted); font-size: 11px; margin: 0 0 6px;">Phenology calendar (${esc(m.calendar_source)}): typical key dates, MM-DD. ${esc(cal.climate_note)}` +
          (cal.dropped && cal.dropped.length ? ` Dropped: ${esc(cal.dropped.join(', '))}.` : '') + `</div>` +
          `<div style="overflow: auto; max-width: 1100px; width: 100%; border: 1px solid var(--panel-border); border-radius: 6px; margin-bottom: 12px;">` +
          `<table style="border-collapse: collapse; width: 100%; font-family: var(--font-mono); font-size: 11.5px; color: var(--text-main);">${head}${body}</table></div>`;
      }
      let panel = document.getElementById('pheno-panel');
      if (!panel) {
        panel = document.createElement('div');
        panel.id = 'pheno-panel';
        panel.style.cssText = 'position: fixed; inset: 0; z-index: 9998; background: rgba(5, 7, 10, 0.95); display: flex; flex-direction: column; align-items: center; padding: 40px 20px 20px; overflow-y: auto;';
        panel.addEventListener('click', e => { if (e.target === panel) panel.style.display = 'none'; });
        document.addEventListener('keydown', e => { if (e.key === 'Escape' && panel.style.display !== 'none') panel.style.display = 'none'; });
        document.body.appendChild(panel);
      }
      panel.innerHTML = `<button onclick="document.getElementById('pheno-panel').style.display='none'" style="position: absolute; top: 14px; right: 18px; padding: 6px 12px;">✕</button>` +
        `<div style="color: var(--text-main); font-size: 13px; margin-bottom: 10px;">🌿 Phenology by date | ${m.view_name || m.view_id} | ${m.id}</div>` + calHtml +
        `<div style="overflow: auto; max-width: 1100px; width: 100%; border: 1px solid var(--panel-border); border-radius: 6px;">` +
        `<table style="border-collapse: collapse; width: 100%; font-family: var(--font-mono); font-size: 11.5px; color: var(--text-main);">${rows}</table></div>`;
      panel.style.display = 'flex';
    }

    // ---------------- Full-screen viewer ----------------
    let lbOpen = false, lbShowRender = true, lbKeystoneHeld = false, lbShowRaw = false;

    function lbRun() {
      const id = document.getElementById('select-replay-run').value;
      return replayRuns.find(r => r.id === id) || null;
    }

    function lbKeystoneFor(run) {
      const vid = run && run.saved_view_id;
      return vid ? keystones[vid] : null;
    }

    function openLightbox() {
      const run = lbRun();
      if (!run) return;
      lbOpen = true;
      lbShowRender = thumbShowsRender;
      const ks = lbKeystoneFor(run);
      if (ks) (new Image()).src = `${PIPE}/api/runs/${encodeURIComponent(ks.run_id)}/file/spatial_twin.png`;  // preload for instant K
      document.getElementById('lightbox').style.display = 'flex';
      renderLightbox();
    }

    function closeLightbox() {
      lbOpen = false;
      lbKeystoneHeld = false;
      document.getElementById('lightbox').style.display = 'none';
    }

    function renderLightbox() {
      const run = lbRun();
      if (!run) { closeLightbox(); return; }
      const img = document.getElementById('lightbox-img');
      const cap = document.getElementById('lightbox-caption');
      const ks = lbKeystoneFor(run);
      if (lbKeystoneHeld && ks) {
        img.src = `${PIPE}/api/runs/${encodeURIComponent(ks.run_id)}/file/spatial_twin.png`;
        cap.textContent = `★ KEYSTONE PLATE for this view (release K to return)`;
        return;
      }
      const showRender = lbShowRender && run.has_twin;
      const raw = showRender && lbShowRaw && run.has_raw;
      img.src = `${PIPE}/api/runs/${encodeURIComponent(run.id)}/file/${raw ? 'spatial_twin_raw.png' : (showRender ? 'spatial_twin.png' : 'viewport_capture.jpg')}`;
      const pos = replayRuns.findIndex(r => r.id === run.id) + 1;
      const seedTxt = run.seed !== null && run.seed !== undefined ? `seed ${run.seed}` : 'seed not recorded';
      cap.textContent = `${runLabel(run)}   |   ${run.address || ''}   |   ${raw ? 'RAW render (before composite)' : (showRender ? (run.composite_applied ? 'composited print' : 'rendered plate') : 'Cesium capture')}   |   ${seedTxt}   |   ${pos} of ${replayRuns.length}`;
    }

    function lbToggle() {
      lbShowRender = !lbShowRender;
      renderLightbox();
    }

    async function lbStep(delta) {
      const sel = document.getElementById('select-replay-run');
      const n = replayRuns.findIndex(r => r.id === sel.value) + delta;
      if (n < 0 || n >= replayRuns.length) return;
      sel.value = replayRuns[n].id;
      renderLightbox();
      await loadReplayScene();   // keep the Replay card in step with the viewer
    }

    document.addEventListener('keydown', (e) => {
      if (!lbOpen) return;
      const k = e.key;
      if (k === 'Escape') closeLightbox();
      else if (k === 'ArrowRight') lbStep(1);
      else if (k === 'ArrowLeft') lbStep(-1);
      else if (k === 'c' || k === 'C') lbToggle();
      else if (k === 'r' || k === 'R') { lbShowRaw = !lbShowRaw; renderLightbox(); }
      else if ((k === 'k' || k === 'K') && !e.repeat) { lbKeystoneHeld = true; renderLightbox(); }
      else return;
      e.preventDefault();
      e.stopPropagation();
    }, true);

    document.addEventListener('keyup', (e) => {
      if (!lbOpen) return;
      if (e.key === 'k' || e.key === 'K') { lbKeystoneHeld = false; renderLightbox(); e.stopPropagation(); }
    }, true);

    function toggleReplayThumb() {
      const id = document.getElementById('select-replay-run').value;
      const run = replayRuns.find(r => r.id === id);
      if (!run || !run.has_twin) return;
      thumbShowsRender = !thumbShowsRender;
      setReplayThumb(id);
    }

    // Conditions that would bake into every print if this plate became the keystone.
    function keystoneWarnings(run) {
      const w = [];
      const weather = (run.weather_resolved || run.weather_mode || '').toUpperCase();
      if (weather === 'RAIN') w.push('Rain: wet, reflective surfaces');
      else if (weather === 'SNOW') w.push('Snow cover');
      else if (!['OVERCAST', 'FOG'].includes(weather)) w.push(`${weather || 'Unknown'} weather: likely direct sun and cast shadows`);
      if (!run.date) {
        w.push('Live date: season unknown');
      } else {
        const m = parseInt(run.date.slice(5, 7), 10);
        const north = (run.latitude || 0) >= 0;
        const dormant = north ? [12, 1, 2, 3].includes(m) : [6, 7, 8, 9].includes(m);
        if (!dormant) w.push('Trees may be in leaf: prints cannot reliably reveal what a canopy hides');
      }
      return w;
    }

    async function loadKeystones() {
      try {
        const resp = await fetch(PIPE + '/api/keystones');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        keystones = (await resp.json()).views || {};
      } catch (e) {
        console.warn('[Keystone] load failed:', e);
        keystones = {};
      }
    }

    function isApprovedKeystone(runId) {
      return Object.values(keystones).some(k => k.run_id === runId);
    }

    // The view the keystone controls act on: the view filter, else the selected run's view.
    function keystoneContextViewId() {
      const viewId = document.getElementById('select-replay-view').value;
      if (viewId) return viewId;
      const run = replayRuns.find(r => r.id === document.getElementById('select-replay-run').value);
      return run ? run.saved_view_id : null;
    }

    function updateSeriesContext() {
      const el = document.getElementById('series-context');
      if (!el) return;
      const viewId = keystoneContextViewId();
      const view = savedViews.find(v => v.id === viewId);
      if (!viewId) { el.textContent = 'Pick a saved view in the Replay card.'; el.style.color = 'var(--text-muted)'; return; }
      const ks = keystones[viewId];
      el.textContent = ks ? `Series for: ${view ? view.name : viewId} (★ keystone approved)` : `${view ? view.name : viewId}: approve a keystone first.`;
      el.style.color = ks ? 'var(--accent-cyan)' : 'var(--text-muted)';
    }

    function updateKeystoneUI() {
      updateSeriesContext();
      const run = replayRuns.find(r => r.id === document.getElementById('select-replay-run').value);
      const approveBtn = document.getElementById('btn-approve-keystone');
      approveBtn.style.display = (run && run.split && run.has_twin && run.saved_view_id && !run.keystone_print_of && !isApprovedKeystone(run.id)) ? 'block' : 'none';
      const status = document.getElementById('keystone-status');
      const viewId = keystoneContextViewId();
      const view = savedViews.find(v => v.id === viewId);
      const ks = viewId ? keystones[viewId] : null;
      if (!viewId) {
        status.textContent = 'Pick a saved view (or a tagged run) to see its keystone.';
      } else if (ks) {
        status.style.color = 'var(--accent-cyan)';
        status.textContent = `★ Keystone for ${view ? view.name : viewId}: approved ${String(ks.approved_utc || '').slice(0, 10)}`;
      } else {
        status.style.color = 'var(--text-muted)';
        status.textContent = `No keystone for ${view ? view.name : viewId} yet.`;
      }
      renderRunFamily(run);
    }

    // Under the run selector: where a keystone came from, which pano it used,
    // and for a source run, every keystone made from it. Each link selects that run.
    function escHtml(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
    function shortTime(r) { const d = runMadeAt(r); return d ? fmtHM(d) : r.id; }

    function renderRunFamily(run) {
      const box = document.getElementById('run-family');
      if (!box) return;
      if (!run) { box.innerHTML = ''; return; }
      const parts = [];
      if (isKeystoneRun(run) && run.replay_of) {
        const src = replayRuns.find(r => r.id === run.replay_of);
        parts.push(`<div>Made from: ${src
          ? `<button class="family-link" data-run="${escHtml(src.id)}">${escHtml(runLabel(src))}</button>`
          : escHtml(run.replay_of)}${run.scene_text_edited ? ' <span class="family-note">(scene text hand-edited)</span>' : ''}</div>`);
      }
      if (isKeystoneRun(run)) {
        const sv = run.streetview;
        if (sv && sv.pano_id) {
          const sq = !sv.size || sv.size === SV_SQUARE;
          const angles = `heading ${sv.heading}°, pitch ${sv.pitch}°, ` + (sq ? `fov ${sv.fov}° (square crop, before 16:9)` : `fov ${sv.fov}° across`) +
            (sv.source_url ? ', from a Maps link' : '');
          const ref = sv.reference === 'detail' ? `<b>detail crop</b> (heading ${sv.detail_heading}°, ${sv.detail_fov}° across, pitch ${sv.detail_pitch}°)`
            : sv.reference === 'full' ? 'full view' : null;
          const how0 = sv.used === false ? `<span class="family-warn">fetch failed, rendered without it${sv.error ? ': ' + escHtml(sv.error) : ''}</span>` : angles;
          const how = ref && sv.used !== false ? `${ref}${sv.reference === 'full' ? ': ' + how0 : ''}` : how0;
          parts.push(`<div>Street View: pano ${escHtml(String(sv.pano_id).slice(0, 10))}… (${escHtml(sv.date || 'undated')}), ${how}` +
            ` <button class="family-link" data-sv="1">use these pano settings</button></div>`);
        } else {
          parts.push(`<div>Street View: <span class="family-note">no reference recorded for this keystone</span></div>`);
        }
      }
      if (run.realigned_from) {
        const src = replayRuns.find(r => r.id === run.realigned_from);
        parts.push(`<div>Realigned from: ${src ? `<button class="family-link" data-run="${escHtml(src.id)}">${escHtml(runLabel(src))}</button>`
          : escHtml(run.realigned_from)} <span class="family-note">(original plate kept in that run)</span></div>`);
      }
      if (run.has_twin && !run.keystone_print_of && !run.date_plate_of && (isKeystoneRun(run) || run.ab)) {
        parts.push(`<div id="run-alignment" data-run-id="${escHtml(run.id)}">${alignmentHtml(run.alignment || alignCache[run.id] || null)}</div>`);
      }
      if (run.lsa_run) parts.push(`<div>Weft pass from: ${escHtml(run.lsa_label || run.lsa_run)}</div>`);
      if (run.ab && run.ab.pair_id) {
        const other = replayRuns.find(r => r.id !== run.id && r.ab && r.ab.pair_id === run.ab.pair_id);
        parts.push(`<div>A/B ${escHtml(run.ab.arm)}, seed ${escHtml(run.ab.seed)}: ${other
          ? `<button class="family-link" data-run="${escHtml(other.id)}">the ${escHtml(other.ab.arm)} arm</button>`
          : '<span class="family-note">the other arm is not in this list</span>'}</div>`);
      }
      const kids = keystonesMadeFrom(run.id);
      if (kids.length) {
        const mark = { approved: '★ approved', superseded: 'superseded', candidate: 'candidate' };
        parts.push(`<div>Keystones made from this run: ` + kids.map(k =>
          `<button class="family-link" data-run="${escHtml(k.id)}">${escHtml(shortTime(k))} ${mark[keystoneStateOf(k.id)]}</button>`).join(' ') + `</div>`);
      }
      box.innerHTML = parts.join('');
      box.querySelectorAll('[data-run]').forEach(b => b.addEventListener('click', () => selectReplayRun(b.dataset.run)));
      const svBtn = box.querySelector('[data-sv]');
      if (svBtn) svBtn.addEventListener('click', () => svUseKeystonePano(run));
      wireAlignment(run);
    }

    // ---------------- Alignment (2026-10-17) ----------------
    // Does a keystone candidate keep the capture's framing? Measured by the server (a few seconds the first time,
    // cached after). Drifted candidates are flagged here, in the approve dialog and after an A/B pair.
    const alignCache = {};

    async function fetchAlignment(runId) {
      if (alignCache[runId]) return alignCache[runId];
      const resp = await fetch(PIPE + `/api/runs/${encodeURIComponent(runId)}/alignment`);
      const d = await resp.json();
      if (!resp.ok) throw new Error(d.detail || `HTTP ${resp.status}`);
      const r = replayRuns.find(x => x.id === runId);
      if (r) r.alignment = d;
      return (alignCache[runId] = d);
    }

    function alignmentHtml(a) {
      if (!a) return 'Framing vs capture: <span class="family-note">measuring...</span>';
      if (a.verdict === 'aligned') return `Framing vs capture: <span class="align-ok">✓ main structure held</span> <span class="family-note">(${escHtml(a.summary)}; ` +
        `measured on the strongest edges, so check the far end of the street by eye: C in the full-screen viewer)</span>`;
      if (a.verdict === 'uncertain') return `Framing vs capture: <span class="family-note">could not be measured reliably; check by eye (C in the full-screen viewer)</span>`;
      return `Framing vs capture: <span class="family-warn">⚠ drifted: ${escHtml(a.summary)}</span>` +
        (a.can_realign
          ? `<div class="align-actions"><button class="btn" data-realign="1">REALIGN AS NEW CANDIDATE</button> ` +
            `<span class="family-note">fixes a whole-frame shift or zoom; it cannot fix a changed perspective</span></div>`
          : ` <span class="family-note">(too far to realign cleanly: render another candidate)</span>`);
    }

    async function wireAlignment(run) {
      const el = document.getElementById('run-alignment');
      if (!el) return;
      const hook = () => {
        const b = el.querySelector('[data-realign]');
        if (b) b.addEventListener('click', () => realignRun(run));
      };
      if (run.alignment || alignCache[run.id]) { hook(); return; }
      try {
        const a = await fetchAlignment(run.id);
        if (el.isConnected && el.dataset.runId === run.id) { el.innerHTML = alignmentHtml(a); hook(); }
      } catch (e) {
        if (el.isConnected) el.innerHTML = `Framing vs capture: <span class="family-note">not measured (${escHtml(e.message)})</span>`;
      }
    }

    async function realignRun(run) {
      const a = alignCache[run.id] || run.alignment;
      if (!confirm(`Make a realigned copy of this plate as a NEW keystone candidate?\n\nThe render ${a ? 'measures: ' + a.summary : 'has drifted'}.` +
        ` Realigning moves the whole image, so it only fully fixes a render that moved as a whole. If the model redrew the perspective` +
        ` (a street receding at a different angle), the main building will line up but the rest will not: compare with C before approving.` +
        ` It will be moved back onto the capture's framing; about ${a ? Math.max(1, Math.round((1 - a.coverage) * 100)) : 2}% of the frame at the edges` +
        ` is filled by mirroring the pixels next to it, so check the edges.\n\nThis run is not changed. Continue?`)) return;
      setReplayStatus('Realigning...', 'var(--accent-cyan)');
      try {
        const resp = await fetch(PIPE + `/api/runs/${encodeURIComponent(run.id)}/realign`, { method: 'POST' });
        const d = await resp.json();
        if (!resp.ok) throw new Error(d.detail || `HTTP ${resp.status}`);
        alignCache[d.run_id] = d.after;
        await loadReplayRuns(false, d.run_id);
        setReplayStatus(`Realigned copy made and selected. The main structure now lines up with the capture; ` +
          `${(d.filled_fraction * 100).toFixed(1)}% of the frame was filled at the edges. Before approving, compare it with the capture (C in the full-screen viewer), ` +
          `especially the far end of the street: if the perspective differs there, render another candidate instead.`, 'var(--accent-cyan)');
      } catch (e) { setReplayStatus(`Realign failed: ${e.message}`, '#ff5252'); }
    }

    function setReplayStatus(msg, color) {
      const el = document.getElementById('replay-status');
      el.style.color = color || 'var(--text-muted)';
      el.textContent = msg;
    }

    function fmtClock(h) {
      if (h === null || h === undefined || h === '') return 'live';
      const hh = Math.floor(h), mm = Math.round((h - hh) * 60);
      return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
    }

    // When a run was made. The server sends "created" (local ISO time); older servers only the
    // archive timestamp, YYYYMMDD_HHMMSS.
    function runMadeAt(r) {
      if (r.created) { const d = new Date(r.created); if (!isNaN(d)) return d; }
      const m = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/.exec(r.timestamp || '');
      return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) : null;
    }
    function fmtHM(d) { return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; }
    function fmtDay(d) { return d ? d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : 'Date unknown'; }

    // What the run is, in words.
    function runKind(r) {
      if (isKeystoneRun(r)) return { approved: '★ Keystone', superseded: 'Keystone, superseded', candidate: 'Keystone candidate' }[keystoneStateOf(r.id)];
      if (r.mode === 'DATE_PLATE' || r.date_plate_of) return 'Date plate';
      if (r.keystone_print_of) return (r.series_frame ? `Series frame ${r.series_frame}` : 'Print') + (r.date_plate_run ? ' from date plate' : '') + (r.composite_applied ? ', composited' : '');
      if (r.replay_of) return r.scene_text_edited ? 'Replay, edited' : 'Replay';
      return 'Synthesize';
    }

    // Label: made-at time and what it is first; scene conditions after, in brackets.
    // Keystones always render neutral midwinter, so their scene date is left out.
    // The day is the heading the run sits under in the list.
    function runLabel(r) {
      const d = runMadeAt(r);
      let label = `${d ? fmtHM(d) : r.id} · ${runKind(r)}`;
      if (!isKeystoneRun(r)) {
        const w = (r.weather_resolved || r.weather_mode || '').toLowerCase();
        const when = r.date ? `${r.date} ${fmtClock(r.time_of_day)}` : 'live clock';
        label += ` (scene ${when}${w ? ', ' + w : ''})`;
      }
      if (r.ab && r.ab.arm) label += ` · A/B ${r.ab.arm}${r.ab.arm === 'B' ? ' (LSA)' : ''}`;
      if (r.realigned_from) label += ' · realigned';
      if (r.alignment && r.alignment.verdict === 'drifted') label += ' · ⚠ drifted';
      else if (r.lsa_run) label += ' · weft pass';
      if (!document.getElementById('select-replay-view').value) label += ` · ${r.saved_view_name || 'no view'}`;
      const kids = keystonesMadeFrom(r.id);
      if (kids.length) {
        const star = kids.some(k => isApprovedKeystone(k.id)) ? '★ ' : '';
        label += ` · ${star}${kids.length} keystone${kids.length > 1 ? 's' : ''}`;
      }
      return label;
    }

    // Keystone candidates made from a run, newest first (the list is already sorted that way).
    function keystonesMadeFrom(runId) {
      return replayRuns.filter(c => isKeystoneRun(c) && c.replay_of === runId);
    }

    // A keystone is a run made with Make keystone, OR any run that was approved as the keystone
    // (Approve accepts any run), now or earlier. Labels, links and the pano card all use this one test.
    function isKeystoneRun(r) {
      return !!r && (!!r.keystone_candidate || keystoneStateOf(r.id) !== 'candidate');
    }

    // Approved now, approved earlier and since replaced, or never approved.
    function keystoneStateOf(runId) {
      if (isApprovedKeystone(runId)) return 'approved';
      const replaced = Object.values(keystones).some(k => (k.history || []).some(h => h.run_id === runId));
      return replaced ? 'superseded' : 'candidate';
    }

    async function fetchReplayRuns(viewId) {
      const resp = await fetch(PIPE + '/api/runs' + (viewId ? `?view_id=${encodeURIComponent(viewId)}` : ''));
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return ((await resp.json()).runs || []).filter(r => r.replayable);
    }

    // keepSelection: stay on the selected run if it is still listed.
    // selectId: the run an action just made; it wins over keepSelection.
    async function loadReplayRuns(keepSelection, selectId) {
      const viewSel = document.getElementById('select-replay-view');
      let viewId = viewSel.value;
      const sel = document.getElementById('select-replay-run');
      const keep = keepSelection ? sel.value : null;
      let filterNote = '';
      await loadKeystones();
      try {
        replayRuns = await fetchReplayRuns(viewId);
        // The new run belongs to another view (or none): show all runs so it can be selected.
        if (selectId && viewId && !replayRuns.some(r => r.id === selectId)) {
          viewSel.value = ''; viewId = '';
          replayRuns = await fetchReplayRuns('');
          filterNote = ' The view filter was set to All runs: the new run is not tagged with that view.';
        }
      } catch (e) {
        console.warn('[Replay] run list failed:', e);
        setReplayStatus('Could not load runs.', '#ff5252');
        return;
      }
      sel.innerHTML = '';
      if (!replayRuns.length) {
        sel.innerHTML = '<option value="">No replayable runs</option>';
        document.getElementById('replay-thumb').style.display = 'none';
        document.getElementById('replay-scene-text').value = '';
        replayOriginalText = '';
        setReplayStatus(viewId ? 'No runs tagged with this view yet.' : '');
        updateKeystoneUI();
        return;
      }
      // Newest first, under a heading for each day.
      replayRuns.sort((a, b) => (runMadeAt(b) || 0) - (runMadeAt(a) || 0));
      let group = null, groupDay = null;
      for (const r of replayRuns) {
        const d = runMadeAt(r), day = fmtDay(d);
        if (day !== groupDay) {
          group = document.createElement('optgroup');
          group.label = day;
          sel.appendChild(group);
          groupDay = day;
        }
        const o = document.createElement('option');
        o.value = r.id;
        o.textContent = runLabel(r);
        o.title = `Made ${d ? d.toLocaleString() : 'at an unknown time'}\n${r.address || ''}\n${r.id}`;
        group.appendChild(o);
      }
      if (selectId && replayRuns.some(r => r.id === selectId)) {
        sel.value = selectId;
        await loadReplayScene();
        const r = selectedReplayRun();
        const src = r && r.replay_of ? replayRuns.find(x => x.id === r.replay_of) : null;
        const what = !r ? 'New run' : r.keystone_candidate ? 'New keystone candidate'
          : r.keystone_print_of ? 'New print' : r.replay_of ? 'New replay' : 'New run';
        const base = document.getElementById('replay-status').textContent;
        setReplayStatus(`${what} selected${r && r.replay_of ? `, made from ${src ? runLabel(src) : r.replay_of}` : ''}.${filterNote} ${base}`.trim(),
          'var(--accent-cyan)');
      } else if (keep && replayRuns.some(r => r.id === keep)) {
        sel.value = keep;
        updateKeystoneUI();
        if (typeof updateSceneState === 'function') updateSceneState();
        if (selectId) setReplayStatus('The new run cannot be replayed (no capture or scene text), so it is not in this list.', '#ffb74d');
      } else {
        await loadReplayScene();
      }
    }

    // Select a run in the list by id, as if picked from the dropdown.
    async function selectReplayRun(id) {
      const sel = document.getElementById('select-replay-run');
      if (!replayRuns.some(r => r.id === id)) {
        document.getElementById('select-replay-view').value = '';
        await loadReplayRuns(false, id);
        return;
      }
      sel.value = id;
      await loadReplayScene();
    }

    async function loadReplayScene() {
      const id = document.getElementById('select-replay-run').value;
      const thumb = document.getElementById('replay-thumb');
      const text = document.getElementById('replay-scene-text');
      updateKeystoneUI();
      svReset();
      lsaReset();
      loadLsaRuns();
      if (!id) { thumb.style.display = 'none'; text.value = ''; replayOriginalText = ''; return; }
      const run = replayRuns.find(r => r.id === id);
      thumbShowsRender = !!(run && run.has_twin);
      setReplayThumb(id);
      thumb.style.display = 'block';
      try {
        const resp = await fetch(`${PIPE}/api/runs/${encodeURIComponent(id)}/scene`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const d = await resp.json();
        text.value = d.documentary_prompt || '';
        replayOriginalText = text.value; if (typeof updateSceneState === 'function') updateSceneState();
        const r = replayRuns.find(x => x.id === id);
        const seedTxt = r && r.seed !== null && r.seed !== undefined ? ` | seed ${r.seed}` : ' | seed not recorded';
        setReplayStatus(`${d.address || ''} (scene text from ${d.loaded_from})${seedTxt}`);
        loadRunPrompt(id);
      } catch (e) {
        console.warn('[Replay] scene load failed:', e);
        text.value = '';
        replayOriginalText = '';
        setReplayStatus('Could not load scene text for this run.', '#ff5252');
      }
    }

    // The Pipeline result tab follows the selected run: the prompt that run actually sent to the image model.
    async function loadRunPrompt(id) {
      const meta = document.getElementById('pipeline-meta'), box = document.getElementById('pipeline-prompt');
      if (!meta || !box) return;
      try {
        const resp = await fetch(`${PIPE}/api/runs/${encodeURIComponent(id)}/prompt`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const p = await resp.json();
        if (id !== document.getElementById('select-replay-run').value) return;   // the selection moved on meanwhile
        const r = replayRuns.find(x => x.id === id);
        const comp = p.composite && typeof p.composite === 'object'
          ? ` · composite ${p.composite.applied ? 'applied' : 'skipped'}${p.composite.reason ? ' (' + p.composite.reason + ')' : ''}` : '';
        meta.textContent = `Run ${r ? runLabel(r) : id} · ${p.date || 'live date'} ${fmtClock(p.time_of_day)} · ${p.weather || ''}${comp}`;
        box.textContent = p.prompt || 'No saved prompt found for this run.';
      } catch (e) {
        meta.textContent = 'Could not load the prompt for this run.';
        box.textContent = '';
      }
    }

    // A seed box: blank means "pick a random one" (the server always records what it used).
    function readSeed(id) {
      const v = document.getElementById(id).value.trim();
      if (!v) return null;
      const n = parseInt(v, 10);
      return Number.isFinite(n) && n >= 0 ? n : null;
    }

    function useRunSeed() {
      const run = selectedReplayRun();
      if (!run || run.seed === null || run.seed === undefined) { setReplayStatus('This run has no recorded seed (made before seeds were recorded).', '#ffb74d'); return; }
      document.getElementById('replay-seed').value = run.seed;
    }

    function selectedReplayRun() {
      const id = document.getElementById('select-replay-run').value;
      return replayRuns.find(r => r.id === id) || null;
    }

    function editedSceneText() {
      const text = document.getElementById('replay-scene-text').value.trim();
      return (text && text !== replayOriginalText.trim()) ? text : null;
    }

    async function makeKeystone() {
      const run = selectedReplayRun();
      if (!run) { setReplayStatus('Pick a run first.', '#ff5252'); return; }
      if (!run.saved_view_id) { setReplayStatus('Keystones need a run tagged with a saved view.', '#ff5252'); return; }
      if (!confirm('Render a keystone candidate from this run?\n\nIt ignores the date, time and weather panels: bare midwinter trees, flat overcast, noon.')) return;
      if (svState && document.getElementById('chk-sv-keystone').checked && svState.size === SV_SQUARE &&
          !confirm('The Street View card shows a square crop from before the 16:9 switch. The keystone will fetch this pano at 16:9 with the same angles, so the reference will show less at the top and bottom than the preview.\n\nContinue?')) return;
      const payload = buildReplayPayload(run, editedSceneText());
      payload.mode = 'KEYSTONE';
      payload.lsa_join = lsaJoinPayload();
      if (svState && document.getElementById('chk-sv-keystone').checked) {
        payload.streetview = svPayload(run);
        console.log(`[Keystone] with Street View reference ${svState.pano_id} (${svState.date})`);
      }
      console.log(`[Keystone] candidate from ${run.id}`);
      resetStepperHUD();
      document.getElementById('loadingOverlay').classList.remove('hidden');
      await streamPipeline(payload);
    }

    async function approveKeystone() {
      const run = selectedReplayRun();
      if (!run) return;
      const view = savedViews.find(v => v.id === run.saved_view_id);
      const replacing = keystones[run.saved_view_id];
      const warnings = keystoneWarnings(run);
      let align = null;
      setReplayStatus('Checking the framing against the capture...', 'var(--accent-cyan)');
      try { align = await fetchAlignment(run.id); } catch (e) { console.warn('[Alignment]', e); }
      setReplayStatus('');
      if (align && align.verdict === 'drifted') warnings.push(`Framing drifted from the capture: ${align.summary}. ` +
        'Prints keep this framing, and Cesium sun shadows will not line up with it' + (align.can_realign ? ' (realign it first: link under the run list)' : ''));
      else if (!align || align.verdict === 'uncertain') warnings.push('Framing could not be checked against the capture: compare by eye (C in the full-screen viewer)');
      const msg = `Approve this plate as the keystone for "${view ? view.name : run.saved_view_id}"?` +
        `\n\nConditions: ${run.date || 'live'} ${fmtClock(run.time_of_day)} ${run.weather_resolved || run.weather_mode || ''}` +
        (warnings.length ? '\n\nNOT NEUTRAL, these will carry into every print:\n- ' + warnings.join('\n- ') : '\n\nConditions are neutral.') +
        (replacing ? '\n\nIt replaces the current keystone (kept on record).' : '') +
        '\n\nEvery print from this view will start from it.';
      if (!confirm(msg)) return;
      try {
        const resp = await fetch(PIPE + '/api/keystones', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run_id: run.id, warnings_acknowledged: warnings })
        });
        if (!resp.ok) throw new Error((await resp.json()).detail || `HTTP ${resp.status}`);
        await loadReplayRuns(true);
        setReplayStatus('Keystone approved.', 'var(--accent-cyan)');
      } catch (e) {
        console.warn('[Keystone] approve failed:', e);
        setReplayStatus(`Approve failed: ${e.message}`, '#ff5252');
      }
    }

    async function printFromKeystone() {
      const viewId = keystoneContextViewId();
      if (!viewId || !keystones[viewId]) { setReplayStatus('This view has no approved keystone yet.', '#ff5252'); return; }
      if (!confirmDropEdits('Print from keystone')) return;
      const view = savedViews.find(v => v.id === viewId);
      const stub = { latitude: view ? view.camera.latitude : 0, longitude: view ? view.camera.longitude : 0 };
      const payload = buildReplayPayload(stub, null);
      payload.mode = 'PRINT';
      payload.print_view_id = viewId;
      payload.replay_of = null;   // the server resolves the keystone
      console.log(`[Print] from keystone of view ${viewId}`);
      // Layer 2 first: an hour print starts from this date's plate; make it once if it doesn't exist yet.
      const date = payload.telemetry.date;
      if (date) {
        let plate = null;
        try { plate = (await (await fetch(`${PIPE}/api/date_plate?view_id=${encodeURIComponent(viewId)}&date=${date}`)).json()).run_id; }
        catch (e) { console.warn('[DatePlate] lookup failed:', e); }
        if (!plate) {
          setReplayStatus(`No date plate for ${date} yet: making it first (the canopy for that date, neutral light), then the print.`, 'var(--accent-cyan)');
          const ok = await runDatePlate(viewId, view, date);
          if (!ok) return;
        }
      }
      resetStepperHUD();
      document.getElementById('loadingOverlay').classList.remove('hidden');
      // Sun shadows: render the keystone's saved view at the print's date and time, without and with
      // Cesium's shadows; the server lays the difference onto the keystone plate (direct sun only).
      if (document.getElementById('chk-sun-shadows')?.checked) {
        if (document.getElementById('chk-live-time').checked) {
          setReplayStatus('Sun shadows skipped: they need a set date and time, not the live clock.', '#ffb74d');
        } else if (!view || !view.camera) {
          setReplayStatus('Sun shadows skipped: the saved view for this keystone was not found.', '#ffb74d');
        } else {
          try {
            const pair = await captureShadowPairAtView(view);
            payload.shadow_base_b64 = pair.base;
            payload.shadow_pass_b64 = pair.pass;
          } catch (e) {
            console.warn('[Sun] shadow pair for the print failed:', e);
            setReplayStatus('Sun shadows skipped: the shadow capture failed (see console). Printing without them.', '#ffb74d');
          }
        }
      }
      await streamPipeline(payload);
    }

    // Make (or remake) the date plate for a view's keystone on a date: the keystone with that date's canopy.
    async function runDatePlate(viewId, view, date) {
      const stub = { latitude: view ? view.camera.latitude : 0, longitude: view ? view.camera.longitude : 0 };
      const payload = buildReplayPayload(stub, null);
      payload.mode = 'DATE_PLATE';
      payload.print_view_id = viewId;
      payload.replay_of = null;
      payload.telemetry.date = date;
      console.log(`[DatePlate] ${viewId} ${date}`);
      resetStepperHUD();
      document.getElementById('loadingOverlay').classList.remove('hidden');
      await streamPipeline(payload);
      try {
        const r = await (await fetch(`${PIPE}/api/date_plate?view_id=${encodeURIComponent(viewId)}&date=${date}`)).json();
        if (r.run_id) return true;
      } catch (e) {}
      setReplayStatus(`The date plate for ${date} was not made (see the server window). Nothing printed.`, '#ff5252');
      return false;
    }

    async function remakeDatePlate() {
      const viewId = keystoneContextViewId();
      if (!viewId || !keystones[viewId]) { setReplayStatus('This view has no approved keystone yet.', '#ff5252'); return; }
      if (document.getElementById('chk-live-time').checked) { setReplayStatus('A date plate needs a set date, not the live clock.', '#ffb74d'); return; }
      const date = document.getElementById('input-date').value;
      if (!confirm(`Make a new date plate for ${date}? Later prints on that date start from the new one; the old one stays in the run list.`)) return;
      await runDatePlate(viewId, savedViews.find(v => v.id === viewId), date);
    }

    // Render a saved view at the strip's date and time twice, without and with Cesium's sun and shadows,
    // then put the camera, field of view, subject marker and shadow switch back as they were.
    async function captureShadowPairAtView(view) {
      const cam = viewer.camera, c = view.camera;
      const saved = { pos: cam.position.clone(), h: cam.heading, p: cam.pitch, r: cam.roll, fov: cam.frustum.fov,
                      subj: subjectEntity ? subjectEntity.show : null,
                      shadows: !!document.getElementById('chk-sun-shadows')?.checked };
      try {
        if (subjectEntity) subjectEntity.show = false;
        if (c.fov_deg) cam.frustum.fov = Cesium.Math.toRadians(c.fov_deg);
        cam.setView({ destination: new Cesium.Cartesian3(c.x, c.y, c.z),
                      orientation: { heading: Cesium.Math.toRadians(c.heading_deg), pitch: Cesium.Math.toRadians(c.pitch_deg),
                                     roll: Cesium.Math.toRadians(c.roll_deg || 0) } });
        syncCesiumTime();
        setSunShadows(false);
        const base = await captureFixedAspect(0.92);
        setSunShadows(true);
        const pass = await captureFixedAspect(0.92);
        console.log(`[Sun] shadow pair rendered at saved view ${view.name}`);
        return { base, pass };
      } finally {
        setSunShadows(saved.shadows);
        cam.frustum.fov = saved.fov;
        cam.setView({ destination: saved.pos, orientation: { heading: saved.h, pitch: saved.p, roll: saved.r } });
        if (subjectEntity && saved.subj !== null) subjectEntity.show = saved.subj;
        updateTelemetryHUD();
      }
    }

    async function replaySelectedRun() {
      const run = selectedReplayRun();
      if (!run) { setReplayStatus('Pick a run first.', '#ff5252'); return; }
      const edited = editedSceneText();
      const payload = buildReplayPayload(run, edited);
      payload.lsa_join = lsaJoinPayload();
      console.log(`[Replay] ${run.id}${edited ? ' (scene text edited)' : ''}${payload.lsa_join ? ' (weft pass)' : ''}`);
      resetStepperHUD();
      document.getElementById('loadingOverlay').classList.remove('hidden');
      await streamPipeline(payload);
    }

    function buildReplayPayload(run, editedText) {
      const isLiveTime = document.getElementById('chk-live-time').checked;
      return {
        screenshot_b64: null,  // the server loads the source run's capture
        telemetry: {
          latitude: run.latitude || 0,   // pose is replaced server-side with the source run's pose
          longitude: run.longitude || 0,
          date: isLiveTime ? null : document.getElementById('input-date').value,
          time_of_day: isLiveTime ? null : parseFloat(document.getElementById('input-time-slider').value),
          timestamp_utc: isLiveTime ? new Date().toISOString() : null,
          lighting_mode: currentLightingMode,
          weather_mode: currentWeatherMode
        },
        marble_input_mode: 'text',
        gemini_budget: parseInt(document.getElementById('slider-gemini-budget').value, 10),
        provider: currentProvider,
        target_model: currentProvider === 'WORLD_LABS'
          ? document.getElementById('select-marble-model').value : 'gemini-3.1-flash-image',
        view_scope: 'FRUSTUM',
        disable_recaption: document.getElementById('chk-disable-recaption').checked,
        use_search_grounding: false,
        replay_of: run.id || null,
        documentary_prompt_override: editedText,
        seed: readSeed('replay-seed'),
        composite: document.getElementById('chk-composite').checked
      };
    }

    function displayResults(data) {
      const links = [
        ['Open world in Marble', data.world_viewer_url],
        ['Gaussian splat (.spz)', data.splat_url],
        ['Collider mesh (.glb)', data.collider_mesh_url],
        ['Source panorama', data.pano_url]
      ].filter(l => !!l[1]);
      if (typeof showPipelineResult === 'function') showPipelineResult(data, links);
      if (data.world_viewer_url) console.log('[Marble] world:', data.world_viewer_url);
    }

    // ---- console helpers -----------------------------------------------
    window.setGlobe = function (v) { viewer.scene.globe.show = !!v; return viewer.scene.globe.show; };
    window.getTileset = function () { return googleTileset; };
    window.terrainReady = function () { return terrainLoaded; };

    window.addEventListener('DOMContentLoaded', initApp);
