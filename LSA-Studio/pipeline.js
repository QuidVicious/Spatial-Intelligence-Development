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
    // A4 (2026-10-21): the stamp follows the camera, not the brief's link. One line before Excavate and
    // before Synthesize says which view a run will be stamped with, or why it will not be.
    function stampInfo() {
      if (!viewer) return { ok: false, text: 'Not stamped with a view: Cesium is not running.' };
      if (!activeSavedView) return { ok: false, text: 'Not stamped with a view: press GO on a saved view, or save this one.' };
      if (!cameraMatchesView(activeSavedView)) return { ok: false, text: `Not stamped: the camera has moved from "${activeSavedView.name}". Press GO to return to it.` };
      return { ok: true, text: `Will be stamped with the view: ${activeSavedView.name}` };
    }
    function updateStampLines() {
      const s = stampInfo();
      ['stamp-line-lsa', 'stamp-line-pipe'].forEach(id => {
        const el = document.getElementById(id);
        if (!el || el.textContent === s.text) return;   // rewrite only on change, so the line can be copied
        el.textContent = s.text;
        el.style.color = s.ok ? 'var(--accent-cyan)' : '#ffb74d';
      });
    }
    setInterval(updateStampLines, 1000);

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
        // A4: saving a view makes it the current view, as GO does, so runs made from here are stamped with it.
        activeSavedView = savedViews.find(v => v.id === rec.id) || activeSavedView;
        updateStampLines();
        setViewsStatus(`Saved and current: ${rec.name}`, 'var(--accent-cyan)');
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
      const applyView = () => viewer.camera.setView({
        destination: new Cesium.Cartesian3(c.x, c.y, c.z),
        orientation: {
          heading: Cesium.Math.toRadians(c.heading_deg),
          pitch: Cesium.Math.toRadians(c.pitch_deg),
          roll: Cesium.Math.toRadians(c.roll_deg || 0)
        }
      });
      applyView();
      // A5 (2026-10-21): the first GO after showing Cesium could leave the camera in the air, apparently pushed up
      // by camera collision against coarse tiles that were still loading; a second GO landed it. Re-apply the
      // view as the tiles load (up to 6 s), unless the user has moved the camera since.
      const goAt = Date.now();
      let userMoved = false;
      const onInput = () => { userMoved = true; };
      viewer.canvas.addEventListener('pointerdown', onInput, { once: true });
      viewer.canvas.addEventListener('wheel', onInput, { once: true });
      const reapply = () => {
        if (userMoved || Date.now() - goAt > 6000) return;
        if (!cameraMatchesView(v)) { applyView(); updateTelemetryHUD(); onCameraSettle(); }
      };
      [700, 1500, 3000, 5800].forEach(ms => setTimeout(reapply, ms));
      if (googleTileset && googleTileset.allTilesLoaded && googleTileset.allTilesLoaded.addEventListener) {
        const off = googleTileset.allTilesLoaded.addEventListener(() => { reapply(); if (typeof off === 'function') off(); });
      }
      updateTelemetryHUD();
      onCameraSettle();
      activeSavedView = v;
      if (typeof placeFromCoords === 'function') {
        const at = v.subject || c;
        placeFromCoords(at.latitude, at.longitude);
      }
      if (v.subject) setSubject(v.subject); else clearSubject(true);
      loadPoisForView(v);
      if (typeof saveFraming === 'function') saveFraming(`saved view ${v.name}`);
      // 58 (2026-10-21): at a saved view the camera locks, so a stray touch cannot lose the framing.
      // 2026-10-22: lock in either frame mode, so switching to Cesium afterwards stays locked too.
      if (typeof setLock === 'function' && !cameraLocked) setLock(true);
      setViewsStatus(typeof cameraLocked !== 'undefined' && cameraLocked
        ? `At: ${v.name}. Camera locked: press Unlock camera above the frame to move it.`
        : `At: ${v.name}. The frame is showing the still: press Show Cesium in the frame, then GO, to see the view and lock the camera there.`, 'var(--accent-cyan)');
      updateStampLines();
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

    // A11 (2026-10-21): one progress card, centred on the frame, for every step that runs on its own
    // (Excavate, the weft pass, the Street View check): what is running, how long, and done or failed.
    let taskTimer = null, taskStartAt = 0;
    function taskCard() {
      let el = document.getElementById('task-card');
      if (el) return el;
      const box = document.getElementById('frame-box');
      if (!box) return null;
      el = document.createElement('div');
      el.id = 'task-card'; el.className = 'task-card'; el.hidden = true; el.setAttribute('role', 'status');
      el.innerHTML = '<div class="task-title"></div><div class="task-msg"></div><div class="task-time"></div>' +
                     '<button class="btn task-close" type="button">OK</button>';
      box.appendChild(el);
      el.querySelector('.task-close').addEventListener('click', () => { el.hidden = true; });
      return el;
    }
    function taskStart(title, msg) {
      const el = taskCard(); if (!el) return;
      el.className = 'task-card running'; el.hidden = false;
      el.querySelector('.task-title').textContent = title;
      el.querySelector('.task-msg').textContent = msg || '';
      el.querySelector('.task-close').hidden = true;
      taskStartAt = Date.now(); clearInterval(taskTimer);
      const tick = () => { el.querySelector('.task-time').textContent = `Running: ${Math.round((Date.now() - taskStartAt) / 1000)} s`; };
      tick(); taskTimer = setInterval(tick, 1000);
    }
    function taskUpdate(msg) { const el = taskCard(); if (el && !el.hidden && msg) el.querySelector('.task-msg').textContent = msg; }
    function taskEnd(ok, msg) {
      const el = taskCard(); if (!el) return;
      clearInterval(taskTimer);
      el.className = 'task-card ' + (ok ? 'done' : 'failed'); el.hidden = false;
      el.querySelector('.task-msg').textContent = msg || '';
      el.querySelector('.task-time').textContent = `${ok ? 'Done' : 'Failed'} after ${Math.round((Date.now() - taskStartAt) / 1000)} s`;
      el.querySelector('.task-close').hidden = false;
      if (ok) setTimeout(() => { if (el.classList.contains('done')) el.hidden = true; }, 8000);
    }
    // "20261021_104856_..." -> "21 Oct, 10:48"
    function fmtRunId(id) {
      const m = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/.exec(id || '');
      if (!m) return id || '';
      const mon = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][+m[2] - 1];
      return `${+m[3]} ${mon}, ${m[4]}:${m[5]}`;
    }
    function hhmm() { const d = new Date(); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; }

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
      if (!subjectPoint) { setSubjectStatus(activeSavedView ? 'No subject set: captures aim at the centre of the frame.' : 'No subject yet: press GO on a saved view to restore its subject, or SET SUBJECT.'); return; }
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
      if (!silent) describeSubject(); else setSubjectStatus('No subject on this view: captures aim at the centre of the frame. SET SUBJECT to add one.');
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
        if (poiDrag) return;
        if (poiPickMode) { addPoiAt(click.position); return; }
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
      // 2026-10-22: drag a point-of-interest marker to move it. The camera is held still while dragging.
      handler.setInputAction(down => {
        const picked = viewer.scene.pick(down.position);
        const i = picked && picked.id ? poiEntities.indexOf(picked.id) : -1;
        if (i < 0 || !(poiPickMode && poiMoveIndex === i)) return;   // only the point whose ↔ is lit can be dragged
        poiDrag = { i, inputs: viewer.scene.screenSpaceCameraController.enableInputs, moved: false };
        viewer.scene.screenSpaceCameraController.enableInputs = false;
        poiEntities[i].show = false;   // so the surface under the marker can be picked
      }, Cesium.ScreenSpaceEventType.LEFT_DOWN);
      handler.setInputAction(move => {
        if (!poiDrag) return;
        const pos = pickSurfaceAt(move.endPosition);
        if (!pos) return;
        Object.assign(poiPoints[poiDrag.i], poiPlace(pos, null));
        poiDrag.last = move.endPosition;
        poiEntities[poiDrag.i].position = new Cesium.Cartesian3(pos.x, pos.y, pos.z);
        poiDrag.moved = true;
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
      handler.setInputAction(() => {
        if (!poiDrag) return;
        const d = poiDrag;
        viewer.scene.screenSpaceCameraController.enableInputs = d.inputs;
        if (poiEntities[d.i]) poiEntities[d.i].show = true;
        if (d.moved) setTimeout(() => { poiDrag = null; }, 0); else poiDrag = null;   // a plain click still places or moves a point
        if (d.moved && d.last) Object.assign(poiPoints[d.i], pickNormalAt(d.last) || { nx: null, ny: null, nz: null });
        if (d.moved) { poiPickMode = false; poiMoveIndex = -1; updatePoiButton(); renderPois(); drawPoiMarkers(); savePois(); setPoiStatus(`Point ${d.i + 1} moved.`, 'var(--accent-cyan)'); }
      }, Cesium.ScreenSpaceEventType.LEFT_UP);
      document.addEventListener('keydown', e => {
        if (poiPickMode && e.key === 'Escape') { poiPickMode = false; poiMoveIndex = -1; updatePoiButton(); renderPois(); setPoiStatus('Cancelled.'); }
        if (subjectPickMode && e.key === 'Escape') { subjectPickMode = false; document.getElementById('btn-set-subject').textContent = '🎯 SET SUBJECT'; describeSubject(); }
      });
      viewer.camera.moveEnd.addEventListener(() => { if (subjectPoint) describeSubject(); });
    }

    // ---------------- Points of interest (B10, 2026-10-22) ----------------
    // Up to five details per saved view, ranked by the director, each with a description the image model reads ahead of
    // the rest of the scene. Stored with the view on the server; the label and the rank stay in this panel.
    let poiPoints = [];          // [{ id, label, description, x, y, z, latitude, longitude, height_m }]
    let poiEntities = [];
    let poiPickMode = false;
    let poiSaveTimer = null;
    let poiLastRemoved = null;   // { point, index } for PUT BACK
    let poiMoveIndex = -1;       // 2026-10-22: MOVE re-places an existing point instead of adding one
    let poiDrag = null;          // { i } while a marker is being dragged
    const POI_MAX = 5;

    function setPoiStatus(msg, color) {
      const el = document.getElementById('poi-status');
      if (!el) return;
      el.style.color = color || 'var(--text-muted)';
      el.textContent = msg || '';
    }
    // A banner at the top of the frame while a point is waiting to be placed or moved: the instruction sits where the eye is.
    function frameHint(msg) {
      let el = document.getElementById('frame-hint');
      const box = document.getElementById('frame-box');
      if (!el && box) {
        el = document.createElement('div'); el.id = 'frame-hint';
        el.style.cssText = 'position:absolute;left:50%;top:10px;transform:translateX(-50%);z-index:7;max-width:calc(100% - 24px);' +
          'padding:6px 14px;border-radius:5px;background:#ffb74d;color:#1b1a17;font:700 13px/1.3 var(--ui);box-shadow:0 4px 14px rgba(0,0,0,.45);pointer-events:none;';
        box.appendChild(el);
      }
      if (!el) return;
      el.textContent = msg || '';
      el.style.display = msg ? 'block' : 'none';
    }
    function updatePoiButton() {
      const b = document.getElementById('btn-add-poi');
      if (!b) return;
      b.textContent = poiPickMode ? (poiMoveIndex >= 0 ? `↔ CLICK THE NEW SPOT FOR POINT ${poiMoveIndex + 1}… (Esc cancels)` : '✚ CLICK THE DETAIL IN THE FRAME… (Esc cancels)') : '✚ ADD POINT OF INTEREST';
      b.disabled = !poiPickMode && poiPoints.length >= POI_MAX;
      frameHint(!poiPickMode ? '' : poiMoveIndex >= 0
        ? `Moving point ${poiMoveIndex + 1}: click its new spot, or drag its marker. Esc or ↔ cancels.`
        : 'New point of interest: click the detail in the frame. Esc cancels.');
    }
    function showPoiMarkers(on) { poiEntities.forEach(e => { e.show = on; }); }
    function drawPoiMarkers() {
      if (!viewer) return;
      poiEntities.forEach(e => viewer.entities.remove(e));
      poiEntities = poiPoints.map((p, i) => viewer.entities.add({
        position: new Cesium.Cartesian3(p.x, p.y, p.z),
        point: { pixelSize: 11, color: Cesium.Color.fromCssColorString('#ffb74d'), outlineColor: Cesium.Color.BLACK,
                 outlineWidth: 2, disableDepthTestDistance: Number.POSITIVE_INFINITY },
        label: { text: `${i + 1}${p.label ? ' ' + p.label : ''}`, font: '11px monospace', pixelOffset: new Cesium.Cartesian2(0, -17),
                 fillColor: Cesium.Color.WHITE, showBackground: true, disableDepthTestDistance: Number.POSITIVE_INFINITY }
      }));
    }
    function loadPoisForView(v) {
      poiPoints = ((v && v.points) || []).map(p => ({ ...p }));
      poiLastRemoved = null;
      renderPois(); drawPoiMarkers(); previewPois();
    }
    function togglePoiPick() {
      if (!activeSavedView) { setPoiStatus('Points of interest are kept with a saved view: press GO on one, or save this view, first.', '#ffb74d'); return; }
      if (!poiPickMode && poiPoints.length >= POI_MAX) { setPoiStatus(`A view holds ${POI_MAX} points: remove one to add another.`, '#ffb74d'); return; }
      poiPickMode = !poiPickMode;
      poiMoveIndex = -1;
      if (poiPickMode) { subjectPickMode = false; setPoiStatus('Click the detail in the Cesium frame. The camera stays locked; clicks still place points.', '#ffb74d'); }
      else setPoiStatus('');
      updatePoiButton();
    }
    // 2026-10-22: which way the clicked surface faces, from the surface a few pixels around the click. Two estimates
    // must agree, or no direction is given (an edge, a thin object, or a broken patch of mesh).
    function pickNormalAt(windowPos) {
      if (!windowPos) return null;
      const at = (dx, dy) => pickSurfaceAt(new Cesium.Cartesian2(windowPos.x + dx, windowPos.y + dy));
      const est = d => {
        const l = at(-d, 0), r = at(d, 0), u = at(0, -d), b = at(0, d);
        if (!l || !r || !u || !b) return null;
        const h = Cesium.Cartesian3.subtract(r, l, new Cesium.Cartesian3());
        const v = Cesium.Cartesian3.subtract(b, u, new Cesium.Cartesian3());
        const n = Cesium.Cartesian3.cross(h, v, new Cesium.Cartesian3());
        if (Cesium.Cartesian3.magnitude(n) < 1e-9) return null;
        Cesium.Cartesian3.normalize(n, n);
        const toCam = Cesium.Cartesian3.subtract(viewer.camera.position, l, new Cesium.Cartesian3());
        if (Cesium.Cartesian3.dot(n, toCam) < 0) Cesium.Cartesian3.negate(n, n);   // the side the camera sees
        return n;
      };
      const a = est(8), b = est(16);
      if (!a || !b || Cesium.Cartesian3.dot(a, b) < 0.85) return null;
      const n = Cesium.Cartesian3.normalize(Cesium.Cartesian3.add(a, b, new Cesium.Cartesian3()), new Cesium.Cartesian3());
      return { nx: n.x, ny: n.y, nz: n.z };
    }
    function poiPlace(pos, windowPos) {
      const c = Cesium.Cartographic.fromCartesian(pos);
      const n = pickNormalAt(windowPos) || { nx: null, ny: null, nz: null };
      return { x: pos.x, y: pos.y, z: pos.z, latitude: Cesium.Math.toDegrees(c.latitude), longitude: Cesium.Math.toDegrees(c.longitude), height_m: c.height, ...n };
    }
    function addPoiAt(windowPos) {
      const pos = pickSurfaceAt(windowPos);
      if (!pos) { setPoiStatus('No surface there. Click a facade, a door, the ground or an object.', '#ff5252'); return; }
      const c = Cesium.Cartographic.fromCartesian(pos);
      if (poiMoveIndex >= 0 && poiPoints[poiMoveIndex]) {
        Object.assign(poiPoints[poiMoveIndex], poiPlace(pos, windowPos));
        const n = poiMoveIndex + 1; poiMoveIndex = -1; poiPickMode = false;
        updatePoiButton(); renderPois(); drawPoiMarkers(); savePois();
        setPoiStatus(`Point ${n} moved.`, 'var(--accent-cyan)');
        return;
      }
      if (poiPoints.length >= POI_MAX) { poiPickMode = false; updatePoiButton(); setPoiStatus(`A view holds ${POI_MAX} points: remove one to add another.`, '#ffb74d'); return; }
      poiPickMode = false;
      poiPoints.push({ id: Date.now().toString(36), label: '', description: '', ...poiPlace(pos, windowPos) });
      updatePoiButton(); renderPois(); drawPoiMarkers();
      setPoiStatus('Point placed. Give it a label for yourself and a description for the image model.', 'var(--accent-cyan)');
      const rows = document.querySelectorAll('#poi-list .poi-row');
      rows[rows.length - 1]?.querySelector('input')?.focus();
      savePois();
    }
    function renderPois() {
      const el = document.getElementById('poi-list');
      if (!el) return;
      el.innerHTML = poiPoints.map((p, i) => `<div class="poi-row" data-i="${i}">` +
        `<div class="poi-head"><span class="poi-rank" title="Rank: the model reads the points in this order">${i + 1}</span>` +
        `<input type="text" maxlength="60" placeholder="Your label (only you see it)" value="${escHtml(p.label || '')}" data-f="label">` +
        `<button class="toggle-btn" data-a="up" title="More important" ${i === 0 ? 'disabled' : ''}>▲</button>` +
        `<button class="toggle-btn" data-a="down" title="Less important" ${i === poiPoints.length - 1 ? 'disabled' : ''}>▼</button>` +
        `<button class="toggle-btn${poiPickMode && poiMoveIndex === i ? ' lit' : ''}" data-a="move" title="Move this point: click here, then click the new spot in the frame; click again to cancel. Dragging the marker also moves it.">↔</button>` +
        `<button class="toggle-btn" data-a="remove" title="Remove this point (PUT BACK restores it)">✕</button></div>` +
        `<textarea maxlength="600" placeholder="What it is, as the model should draw it: shape, material, colour, what it is fixed to" data-f="description">${escHtml(p.description || '')}</textarea>` +
        `<div class="poi-where" data-where="${i}"></div></div>`).join('') +
        (poiLastRemoved ? `<div class="poi-where">Removed: ${escHtml(poiLastRemoved.point.label || 'a point')}. <button class="lsa-added-btn" data-a="putback">PUT BACK</button></div>` : '');
      el.querySelectorAll('.poi-row').forEach(row => {
        const i = +row.dataset.i;
        row.querySelectorAll('[data-f]').forEach(f => f.addEventListener('input', () => {
          poiPoints[i][f.dataset.f] = f.value;
          if (f.dataset.f === 'label') drawPoiMarkers();
          clearTimeout(poiSaveTimer); poiSaveTimer = setTimeout(savePois, 700);
        }));
        row.querySelectorAll('[data-a]').forEach(b => b.addEventListener('click', () => poiAction(i, b.dataset.a)));
      });
      el.querySelector('[data-a="putback"]')?.addEventListener('click', () => poiAction(-1, 'putback'));
      updatePoiButton();
    }
    function poiAction(i, a) {
      if (a === 'up' && i > 0) [poiPoints[i - 1], poiPoints[i]] = [poiPoints[i], poiPoints[i - 1]];
      else if (a === 'down' && i < poiPoints.length - 1) [poiPoints[i + 1], poiPoints[i]] = [poiPoints[i], poiPoints[i + 1]];
      else if (a === 'move') {
        if (!activeSavedView) return;
        if (poiPickMode && poiMoveIndex === i) {   // pressed again: cancel the waiting move
          poiPickMode = false; poiMoveIndex = -1; updatePoiButton(); renderPois(); setPoiStatus('Move cancelled.'); return;
        }
        poiMoveIndex = i; poiPickMode = true; subjectPickMode = false; updatePoiButton(); renderPois();
        setPoiStatus(`Click the new spot for point ${i + 1} in the frame. Press ↔ again or Esc to cancel. (Dragging a marker moves it too.)`, '#ffb74d');
        return;
      }
      else if (a === 'remove') { poiLastRemoved = { point: poiPoints[i], index: i }; poiPoints.splice(i, 1); }
      else if (a === 'putback' && poiLastRemoved && poiPoints.length < POI_MAX) {
        poiPoints.splice(Math.min(poiLastRemoved.index, poiPoints.length), 0, poiLastRemoved.point); poiLastRemoved = null; }
      renderPois(); drawPoiMarkers(); savePois();
    }
    async function savePois() {
      clearTimeout(poiSaveTimer);
      if (!activeSavedView) return;
      const id = activeSavedView.id;
      try {
        const r = await fetch(PIPE + '/api/views/' + encodeURIComponent(id) + '/points', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ points: poiPoints }) });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        const sv = savedViews.find(v => v.id === id);
        if (sv) sv.points = d.view.points;
        if (activeSavedView && activeSavedView.id === id) activeSavedView.points = d.view.points;
        showPoiPreview(d);
        setPoiStatus(`Saved with the view "${activeSavedView ? activeSavedView.name : id}" at ${hhmm()}.`, 'var(--accent-cyan)');
      } catch (e) { setPoiStatus('Points not saved: ' + e.message, '#ff5252'); }
    }
    async function previewPois() {
      if (!activeSavedView) { showPoiPreview(null); return; }
      try {
        const r = await fetch(PIPE + '/api/views/' + encodeURIComponent(activeSavedView.id) + '/points/preview');
        showPoiPreview(r.ok ? await r.json() : null);
      } catch (e) { showPoiPreview(null); }
    }
    function showPoiPreview(d) {
      const box = document.getElementById('poi-preview-box'), pre = document.getElementById('poi-preview');
      if (!box || !pre) return;
      box.hidden = !(d && d.block);
      pre.textContent = d && d.block ? d.block : '';
      ((d && d.points) || []).forEach(p => {
        const i = poiPoints.findIndex(q => q.id === p.id);
        const w = document.querySelector(`#poi-list [data-where="${i}"]`);
        if (w) w.textContent = `In the frame: ${p.position}.`;
      });
      poiPoints.forEach((p, i) => { if (!(p.description || '').trim()) { const w = document.querySelector(`#poi-list [data-where="${i}"]`); if (w) w.textContent = 'No description yet: this point is not sent to the model.'; } });
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
      showPoiMarkers(false);
      
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
      showPoiMarkers(true);
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

    // 2026-10-23: a run's rendered image is its newest edited version when it has one (the edit pass keeps the original as v0).
    function plateUrl(runId, editVersion) {
      return editVersion ? `${PIPE}/api/runs/${encodeURIComponent(runId)}/edits/image/${editVersion}?v=${editVersion}`
                         : `${PIPE}/api/runs/${encodeURIComponent(runId)}/file/spatial_twin.png`;
    }
    function setReplayThumb(id) {
      const thumb = document.getElementById('replay-thumb');
      const run = replayRuns.find(r => r.id === id);
      thumb.src = thumbShowsRender ? plateUrl(id, run && run.edit_version) : `${PIPE}/api/runs/${encodeURIComponent(id)}/file/viewport_capture.jpg`;
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
      taskStart('Street View check (FINISHING PASS)', `Reading pano ${svState.pano_id} into the scene text. Usually 20 to 40 s.`);
      try {
        const resp = await fetch(PIPE + '/api/streetview/rewrite', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_id: run.id, pano_id: svState.pano_id, heading: svState.heading, pitch: svState.pitch,
                                 fov: svState.fov, date: svState.date, scene_text: before })
        });
        const d = await resp.json();
        if (!resp.ok) throw new Error(d.detail || `HTTP ${resp.status}`);
        if (!d.changed) { setSvStatus('The pano matched the scene text; nothing was changed.', 'var(--accent-cyan)'); lastFinish = null; renderFinishReport(d);
                          taskEnd(true, 'Nothing changed: the pano matched the scene text.'); return; }
        svPreRewriteText = before;
        if (lsaJoin) lsaJoin.finishing_after = true;   // A/B: only the B text has had the finishing pass
        box.value = d.scene_text; if (typeof updateSceneState === 'function') updateSceneState();
        box.scrollTop = 0;
        document.getElementById('btn-sv-undo').style.display = '';
        lastFinish = { text: d.scene_text, at: hhmm() };
        renderFinishReport(d);
        taskEnd(true, `Scene text updated (${before.length} to ${d.scene_text.length} characters). Read the report under the Street View card.`);
        setSvStatus(`Finishing pass from pano ${d.pano_id} (${d.date || 'undated'}): ${before.length} → ${d.scene_text.length} chars.` +
          (d.removed && d.removed.length ? ` It REMOVED structure: ${d.removed.join(', ')}. Check the report below.` : '') +
          ' Review it before MAKE KEYSTONE; UNDO restores the previous text.', d.removed && d.removed.length ? '#ffb74d' : 'var(--accent-cyan)');
      } catch (e) { setSvStatus(e.message, '#ff5252'); taskEnd(false, e.message); }
    }
    let lastFinish = null;   // A14: the text the finishing report describes, and when

    // A14 (2026-10-21): a report says so when the text has changed since it was made.
    function markReportsStale() {
      const box = document.getElementById('replay-scene-text');
      if (!box) return;
      const v = box.value.trim();
      const mark = (id, rec, who) => {
        const el = document.getElementById(id);
        if (!el) return;
        let n = el.querySelector('.stale-note');
        const stale = !!rec && !el.hidden && v !== (rec.text || '').trim();
        if (stale && !n) { n = document.createElement('div'); n.className = 'stale-note'; el.prepend(n); }
        if (n) { n.hidden = !stale; if (stale) n.textContent = `This report is from the ${who} at ${rec.at}. The text has been edited since, so parts of it may no longer apply.`; }
      };
      mark('lsa-join-added', lsaJoin && { text: lsaJoin.text_after, at: lsaJoin.at }, 'weft pass');
      mark('sv-finish-report', lastFinish, 'Street View check');
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
      const warm = [...new Set(((d.scene_text || '').match(/\b(honey|golden|gold|ochre|amber|tawny)\b/gi) || []).map(w => w.toLowerCase()))];
      el.innerHTML = removedHtml(d.removed, 'the finishing pass') + seasonNoteHtml(d.date) + wordWarningsHtml(d.warnings) +
        (warm.length ? `<div class="lsa-added-head" style="color: #ffb74d;">Warm colour words in the text: ${warm.map(escHtml).join(', ')}</div>` +
          '<div class="lsa-added-note">Usually sunlight in the pano, not the stone. Replace them with the colour the stone has in flat overcast light (buff-grey, grey-tan, pale grey).</div>' : '') +
        `<div class="lsa-added-head">Added from the pano</div>` +
        (added.length ? added.map(a => `<div class="lsa-added-text">"${escHtml(a.phrase)}" <span class="lsa-added-note">${escHtml(a.note || '')}</span></div>`).join('')
                      : '<div class="lsa-added-note">Nothing structural added.</div>') +
        `<div class="lsa-added-head">Where the pano seems to disagree (not applied)</div>` +
        (conflicts.length ? conflicts.map(c => `<div class="lsa-added-text">${escHtml(c)}</div>`).join('') +
          '<div class="lsa-added-note">The scene text was kept. If the pano is right, edit the text by hand (and your Scene layout).</div>'
                          : '<div class="lsa-added-note">No disagreements reported.</div>');
      el.hidden = false;
      markReportsStale();
    }

    // A2 (2026-10-21): a pano's season shows in the report; summer sun pushes colours warm.
    function seasonOf(dateStr, lat) {
      const m = /^(\d{4})-(\d{2})/.exec(dateStr || '');
      if (!m) return null;
      const month = parseInt(m[2], 10), south = (lat || 0) < 0;
      const north = ['winter', 'winter', 'spring', 'spring', 'spring', 'summer', 'summer', 'summer', 'autumn', 'autumn', 'autumn', 'winter'];
      const flip = { winter: 'summer', summer: 'winter', spring: 'autumn', autumn: 'spring' };
      const s = north[month - 1];
      return south ? flip[s] : s;
    }
    function seasonNoteHtml(dateStr) {
      const lat = svState && svState.lat;
      const season = seasonOf(dateStr || (svState && svState.date), lat);
      if (!season) return '';
      const warm = season === 'summer' || season === 'spring';
      return `<div class="lsa-added-note">Pano taken in ${escHtml(dateStr || svState.date)} (${season}).` +
        (warm ? ' Sunlit panos push colours warm: check that no "honey", "golden" or "ochre" came in.' : '') + '</div>';
    }
    // A1 (2026-10-21): flagged words say why they are flagged.
    function wordWarningsHtml(words) {
      if (!words || !words.length) return '';
      return `<div class="lsa-added-head">Words to check</div><div class="lsa-added-text">${words.map(escHtml).join(', ')}</div>` +
        '<div class="lsa-added-note">Weather, light and season words pull the render toward that weather: describe the mark instead ' +
        '(pale, cleaner, streaked, stained, bleached). Compass words become exposure words (sheltered, exposed). Street and place names become position words.</div>';
    }

    function svUndoRewrite() {
      if (svPreRewriteText === null) return;
      document.getElementById('replay-scene-text').value = svPreRewriteText; if (typeof updateSceneState === 'function') updateSceneState();
      svPreRewriteText = null;
      document.getElementById('btn-sv-undo').style.display = 'none';
      lastFinish = null;
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
    // 70 (2026-10-22): after an Excavate the new run is selected and ADD LSA SURFACES lights up (selectId).
    async function loadLsaRuns(selectId) {
      const sel = document.getElementById('lsa-join-run');
      if (!sel) return;
      try { const r = await fetch('/api/runs'); lsaRuns = r.ok ? await r.json() : []; } catch (e) { lsaRuns = []; }
      lsaRuns = (Array.isArray(lsaRuns) ? lsaRuns : []).filter(lsaUsable);
      const prev = sel.value;   // A8: a hand pick survives a refresh
      const run = selectedReplayRun();
      const viewId = run ? run.saved_view_id : null;
      const mine = lsaRuns.filter(r => viewId && r.saved_view_id === viewId);
      const rest = lsaRuns.filter(r => !mine.includes(r));
      const opt = r => `<option value="${escHtml(r.run_id)}" title="${escHtml(r.subject || '')}">${escHtml(fmtLsaRun(r))}</option>`;
      if (!lsaRuns.length) { sel.innerHTML = '<option value="">No LSA run yet: press Excavate in the brief on the left</option>'; lsaPreview(); return; }
      sel.innerHTML = '<option value="">Choose an LSA run</option>' +
        (mine.length ? `<optgroup label="Made at this view">${mine.map(opt).join('')}</optgroup>` : '') +
        `<optgroup label="${mine.length ? 'Other LSA runs' : 'LSA runs (none made at this view)'}">${rest.map(opt).join('')}</optgroup>`;
      const fresh = selectId && lsaRuns.some(r => r.run_id === selectId);
      const kept = !fresh && prev && lsaRuns.some(r => r.run_id === prev);
      sel.value = fresh ? selectId : kept ? prev : (mine.length ? mine[0].run_id : '');
      if (fresh) {
        setLsaStatus(`New LSA run selected: ${fmtRunId(selectId)}. Next: ADD LSA SURFACES brings it into the scene text of the selected capture.`, 'var(--accent-cyan)');
        document.getElementById('btn-lsa-weave')?.classList.add('lit');
      } else if (run && !lsaJoin && !kept) setLsaStatus(mine.length ? 'The newest LSA run made at this view is selected. Check the preview below.'
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
      const cur = typeof readShot === 'function' ? readShot() : null;
      const samePlace = cur && (cur.place || '').trim() === (shot.place || '').trim();
      const older = samePlace && (cur.layout || '').trim() && (cur.layout || '').trim() !== layout;
      brief.textContent = (older ? 'This run was made with an earlier scene layout than the one in your brief now. The weft pass uses your brief\'s layout; the run\'s analysis was written from the earlier one, so a new Excavate may be worth it.\n\n' : '') +
        `${s.label || shot.place || id} · ${made} · ${s.instruction || ''} · ${stamp}\n` +
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
      // 68 (2026-10-22): the layout comes from the brief as it is now when the brief is for the same place as the
      // LSA run, so a corrected layout is used at once; otherwise from the run's own brief.
      const cur = typeof readShot === 'function' ? readShot() : null;
      const useBrief = !!(cur && (cur.layout || '').trim() && (cur.place || '').trim() === ((lsa.shot || {}).place || '').trim());
      const layoutShot = useBrief ? cur : lsa.shot;
      const layout = lsaDirectorLayout(layoutShot);
      document.getElementById('btn-lsa-weave')?.classList.remove('lit');
      setLsaStatus('Weaving the analysis and your layout into the scene text (about a minute)...', 'var(--accent-cyan)');
      taskStart('Weft pass (ADD LSA SURFACES)', 'Weaving the LSA run and your layout into the scene text. Usually about a minute.');
      try {
        const resp = await fetch(PIPE + '/api/lsa/weave', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_id: run.id, scene_text: before, analysis: lsa.analysis, lsa_run_id: id, director_layout: layout || null })
        });
        const d = await resp.json();
        if (!resp.ok) throw new Error(d.detail || `HTTP ${resp.status}`);
        if ((selectedReplayRun() || {}).id !== run.id) { setLsaStatus('The selected run changed while the pass ran; nothing was changed.', '#ffb74d');
          taskEnd(false, 'The selected run changed while the pass ran; nothing was changed.'); return; }
        const s = lsa.settings || {};
        lsaJoin = { run_id: id, label: s.label || id, instruction: s.instruction || null,
                    text_before: (lsaJoin ? lsaJoin.text_before : before), text_after: d.scene_text,
                    ecology: d.ecology || '', added_structure: (d.added_structure || []).map(a => ({ ...a, decision: null })), removed: d.removed || [],
                    species_to_verify: d.species_to_verify || [],
                    set_aside: d.set_aside || '', not_added: d.not_added || '', finishing_after: false,
                    director_layout_used: !!layout, at: hhmm(),
                    layout_from: useBrief ? 'brief' : 'run', layout_text: ((layoutShot || {}).layout || '') };
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
        setLsaStatus(`Weft pass at ${lsaJoin.at}, using the LSA run of ${fmtRunId(id)}` + (s.label ? ` (${s.label})` : '') +
          (layout ? (useBrief ? ' and the scene layout in your brief now' : ' and the scene layout saved with that run') : ', with no scene layout (the run has none)') +
          `: ${before.length} → ${d.scene_text.length} chars.` +
          (added.length ? ` Structure added: ${added.length - nProp} confirmed, ${nProp} proposed (listed below).` : ' No structure added.') +
          (d.warnings && d.warnings.length ? ` Words to check: ${d.warnings.join(', ')} (weather, light and season words pull the render toward that weather: describe the mark instead; place names become position words).` : '') +
          ' Review it in the editor before making a keystone; UNDO restores the previous text.',
          d.warnings && d.warnings.length ? '#ffb74d' : 'var(--accent-cyan)');
        taskEnd(true, `Scene text updated (${before.length} to ${d.scene_text.length} characters). Read the report under the weft pass.`);
      } catch (e) { setLsaStatus(e.message, '#ff5252'); taskEnd(false, e.message); }
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
        const state = a.decision === 'removed' ? `<span class="lsa-added-done">removed</span><button class="lsa-added-btn" data-i="${i}" data-act="putback" title="Put the words back where they were">PUT BACK</button>`
          : a.decision === 'kept' ? '<span class="lsa-added-done">kept</span>'
          : `<button class="lsa-added-btn" data-i="${i}" data-act="keep">KEEP</button>` +
            `<button class="lsa-added-btn" data-i="${i}" data-act="remove"${a.found ? '' : ' disabled title="Not found word for word in the text: edit it by hand"'}>REMOVE</button>`;
        return `<div class="lsa-added-row ${a.status}${a.decision ? ' decided' : ''}">` +
          `<span class="lsa-added-tag ${a.status}">${tag}</span>` +
          `<span class="lsa-added-text">"${escHtml(a.phrase)}" <span class="lsa-added-note">${escHtml(src)}${a.note ? ': ' + escHtml(a.note) : ''}</span></span>` +
          `<span class="lsa-added-acts">${state}</span></div>` + extraWordsHtml(a) +
          (a.decision === 'removed' && a.sentence_after ? `<div class="lsa-added-sentence${a.join_doubt ? ' doubt' : ''}">` +
            `<div><b>Was:</b> ${escHtml(a.sentence_before)}</div><div><b>Now:</b> ${escHtml(a.sentence_after)}</div>` +
            (a.join_doubt ? '<div class="lsa-added-note">This sentence may need a word where the phrase was: edit it in the scene text.</div>' : '') + '</div>' : '');
      }).join('');
      el.hidden = false;
      el.querySelectorAll('.lsa-added-btn').forEach(b => b.addEventListener('click', () => lsaDecide(+b.dataset.i, b.dataset.act)));
      markReportsStale();
    }

    function lsaDecide(i, act) {
      const a = lsaJoin && lsaJoin.added_structure[i];
      if (!a) return;
      if (act === 'remove') {
        const box = document.getElementById('replay-scene-text');
        if (!box.value.includes(a.phrase)) { setLsaStatus(`"${a.phrase}" is no longer in the text word for word: edit it by hand.`, '#ffb74d'); return; }
        const res = removeCleanly(box.value, a.phrase);
        a.text_before_remove = box.value; a.text_after_remove = res.text;
        box.value = res.text;
        a.sentence_before = res.before; a.sentence_after = res.after; a.join_doubt = res.doubt;
        lsaJoin.text_after = box.value;   // a removal from the list is part of the pass, not a hand edit
        if (typeof updateSceneState === 'function') updateSceneState();
        setLsaStatus(res.doubt ? `Removed "${a.phrase}". The sentence may need a word: it is shown under the item.` : `Removed "${a.phrase}".`,
                     res.doubt ? '#ffb74d' : 'var(--accent-cyan)');
      }
      if (act === 'putback') {
        // 69 (2026-10-22): a removal is undone in one click where it happened, instead of a confirm on every REMOVE.
        const box = document.getElementById('replay-scene-text');
        const gone = !a.sentence_after || a.sentence_after.startsWith('(sentence removed');
        if (box.value === a.text_after_remove) box.value = a.text_before_remove;
        else if (!gone && box.value.includes(a.sentence_after)) box.value = box.value.replace(a.sentence_after, a.sentence_before);
        else { setLsaStatus(`The text has changed since "${a.phrase}" was removed, so it cannot be put back automatically. The sentence it was in is shown under the item: paste it back by hand.`, '#ffb74d'); return; }
        lsaJoin.text_after = box.value;
        a.decision = null; a.sentence_before = a.sentence_after = undefined;
        if (typeof updateSceneState === 'function') updateSceneState();
        setLsaStatus(`Put back "${a.phrase}".`, 'var(--accent-cyan)');
        renderLsaAdded();
        return;
      }
      a.decision = act === 'remove' ? 'removed' : 'kept';
      renderLsaAdded();
    }

    // 71 (2026-10-22): a "confirmed from your layout" phrase can carry words the layout never used ("mutule",
    // "fluted"); list them, so a model's addition does not pass as the director's.
    function extraWordsHtml(a) {
      if (!lsaJoin || a.status !== 'confirmed' || a.source !== 'layout' || !lsaJoin.layout_text) return '';
      const known = (lsaJoin.layout_text + ' ' + (lsaJoin.text_before || '')).toLowerCase();
      const has = w => known.includes(w) || (w.endsWith('s') && known.includes(w.slice(0, -1)));
      const extra = [...new Set((a.phrase.toLowerCase().match(/[a-z][a-z-]{3,}/g) || []).filter(w => !has(w)))];
      if (!extra.length) return '';
      return `<div class="lsa-added-sentence doubt"><div class="lsa-added-note">Not in your layout: <b>${extra.map(escHtml).join(', ')}</b>. ` +
        'The model added these; check them before keeping the item.</div></div>';
    }

    // A13 (2026-10-21): take a phrase out with the word that joined it, repair the punctuation, and report the
    // sentence before and after. "doubt" means the sentence still ends a clause on a joining word, so it needs reading.
    function removeCleanly(text, phrase) {
      const i = text.indexOf(phrase);
      let sStart = 0;
      for (const m of text.slice(0, i).matchAll(/[.!?]\s+|\n/g)) sStart = m.index + m[0].length;
      const tail = /[.!?](?=\s|$)|\n/g; tail.lastIndex = i + phrase.length;
      const t = tail.exec(text);
      const sEnd = t ? t.index + (t[0] === '\n' ? 0 : 1) : text.length;
      const before = text.slice(sStart, sEnd).trim();
      const esc = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const joins = [
        new RegExp(`\\s*,\\s*(?:and|with|or)?\\s*${esc}`),   // ", and PHRASE" or ", PHRASE"
        new RegExp(`\\s+(?:and|with|or)\\s+${esc}`),          // " and PHRASE"
        new RegExp(`\\s*;\\s*${esc}`),                        // "; PHRASE"
        new RegExp(`^${esc}\\s*(?:,|\\band\\b|\\bwith\\b)\\s*`), // "PHRASE, ..." opening the sentence
        new RegExp(`\\s*(?:\\b(?:a|an|the)\\s+)?${esc}`)];   // "a PHRASE": the article goes with it
      let sent = before, listFix = false;
      for (const [k, re] of joins.entries()) {
        const m = re.exec(sent); if (!m) continue;
        let head = sent.slice(0, m.index);
        // "A, B and PHRASE" leaves "A, B": put the "and" back between the last two items.
        if ((k === 0 || k === 1) && /\band\b/.test(m[0])) {
          const c = head.lastIndexOf(', ');
          if (c >= 0 && !/[;:]/.test(head.slice(c))) { head = head.slice(0, c) + ' and ' + head.slice(c + 2); listFix = true; }
        }
        sent = head + sent.slice(m.index + m[0].length); break;
      }
      sent = sent.replace(/\s+([,;.:])/g, '$1').replace(/([,;:])\s*([,;.:])/g, '$2').replace(/[ \t]{2,}/g, ' ')
                 .replace(/^\s*[,;:]\s*/, '').trim();
      if (/^[a-z]/.test(sent)) sent = sent[0].toUpperCase() + sent.slice(1);
      const keep = sent.replace(/[.,;:!?]/g, ' ').trim().split(/\s+/).filter(Boolean).length >= 3;
      const after = keep ? sent : '';
      const orphan = /\b(?:above|below|under|over|beneath|of|in|on|with|by|to|from|into|onto|behind|along)\s+(?:with|of|in|on|by|to|from|and|above|below)\b/i;
      const doubt = keep && listFix || keep && orphan.test(after) || keep && /\b(?:and|with|or|of|into|onto|beneath|under|by|from|the|a|an)\s*(?:[,;.:]|$)/i.test(after);
      const out = (text.slice(0, sStart) + after + (after && text.slice(sEnd) && !/^\s/.test(text.slice(sEnd)) ? ' ' : '') + text.slice(sEnd))
                    .replace(/[ \t]{2,}/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
      return { text: out, before, after: after || '(sentence removed: nothing was left of it)', doubt };
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
      if (!confirm(`Make two keystone candidates from this run's capture, both with seed ${seed} and ${useSv ? `the same pano image (${svState.pano_id})` : 'TEXT ONLY (no pano image)'}:\n\n` +
        `A: the scene text before the weft pass (${textA.length} chars)\nB: the scene text after it (${textB.length} chars)\n\n` +
        (warn.length ? 'NOTE: ' + warn.join(' ') + '\n\n' : '') + 'That is two renders. Continue?')) return;
      const pair = 'ab_' + Date.now().toString(36);
      const build = (text, arm) => {
        const fromCapture = !!(run.keystone_candidate && run.replay_of);
        const p = buildReplayPayload(run, (fromCapture || text !== replayOriginalText.trim()) ? text : null);
        if (fromCapture) p.replay_of = run.replay_of;   // A6: always from the capture, with the text sent explicitly
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
      if (ks) (new Image()).src = plateUrl(ks.run_id, ks.edit_version);  // preload for instant K
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
        img.src = plateUrl(ks.run_id, ks.edit_version);
        cap.textContent = `★ KEYSTONE PLATE for this view${ks.edit_version ? `, edited version ${ks.edit_version}` : ''} (release K to return)`;
        return;
      }
      const showRender = lbShowRender && run.has_twin;
      const raw = showRender && lbShowRaw && run.has_raw;
      img.src = raw ? `${PIPE}/api/runs/${encodeURIComponent(run.id)}/file/spatial_twin_raw.png`
                    : (showRender ? plateUrl(run.id, run.edit_version) : `${PIPE}/api/runs/${encodeURIComponent(run.id)}/file/viewport_capture.jpg`);
      const pos = replayRuns.findIndex(r => r.id === run.id) + 1;
      const seedTxt = run.seed !== null && run.seed !== undefined ? `seed ${run.seed}` : 'seed not recorded';
      cap.textContent = `${runLabel(run)}   |   ${run.address || ''}   |   ${raw ? 'RAW render (before composite)' : (showRender ? (run.composite_applied ? 'composited print' : 'rendered plate') + (run.edit_version ? `, edited version ${run.edit_version}` : '') : 'Cesium capture')}   |   ${seedTxt}   |   ${pos} of ${replayRuns.length}`;
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
      // 2026-10-23: an approved keystone can be approved again after edits, so prints start from the edited version.
      const ksRec = run && run.saved_view_id ? keystones[run.saved_view_id] : null;
      const editedSince = !!(ksRec && ksRec.run_id === (run && run.id) && (run.edit_version || 0) !== (ksRec.edit_version || 0));
      approveBtn.style.display = (run && run.split && run.has_twin && run.saved_view_id && !run.keystone_print_of && (!isApprovedKeystone(run.id) || editedSince)) ? 'block' : 'none';
      approveBtn.textContent = editedSince ? `✅ APPROVE EDITED VERSION ${run.edit_version || 0} AS KEYSTONE` : '✅ APPROVE AS KEYSTONE';
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
        sel.innerHTML = `<option value="">${viewId ? 'No capture of this view yet: press Synthesize at the top of this column' : 'No captures yet: press Synthesize at the top of this column'}</option>`;
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
      // A6 (2026-10-21): a keystone is always made from the capture. If a candidate is selected, use its capture.
      const sourceId = (run.keystone_candidate && run.replay_of) ? run.replay_of : run.id;
      const srcRun = replayRuns.find(r => r.id === sourceId);
      const useSv = !!(svState && document.getElementById('chk-sv-keystone').checked);
      // A7: the dialog says plainly whether a pano image goes with the render.
      if (!confirm(`Render a keystone candidate from the capture ${srcRun ? runLabel(srcRun) : sourceId}?` +
        (sourceId !== run.id ? '\n(The selected run is a candidate; the new one is made from its capture, not from the candidate.)' : '') +
        `\n\n${useSv ? `WITH PANO IMAGE: ${svState.pano_id} (${svState.date || 'undated'})` : 'TEXT ONLY: no pano image is sent.'}` +
        '\n\nIt ignores the date, time and weather panels: bare midwinter trees, flat overcast, noon.')) return;
      if (useSv && svState.size === SV_SQUARE &&
          !confirm('The Street View card shows a square crop from before the 16:9 switch. The keystone will fetch this pano at 16:9 with the same angles, so the reference will show less at the top and bottom than the preview.\n\nContinue?')) return;
      // From a candidate's capture, the text in the box is always sent: unedited, the server would otherwise
      // fall back to the capture's own original text, not the candidate's.
      const boxText = document.getElementById('replay-scene-text').value.trim();
      const payload = buildReplayPayload(run, sourceId !== run.id ? (boxText || null) : editedSceneText());
      payload.replay_of = sourceId;
      payload.mode = 'KEYSTONE';
      payload.lsa_join = lsaJoinPayload();
      if (svState && document.getElementById('chk-sv-keystone').checked) {
        payload.streetview = svPayload(run);
        console.log(`[Keystone] with Street View reference ${svState.pano_id} (${svState.date})`);
      }
      console.log(`[Keystone] candidate from capture ${sourceId}${sourceId !== run.id ? ` (selected candidate ${run.id})` : ''}`);
      resetStepperHUD();
      document.getElementById('loadingOverlay').classList.remove('hidden');
      await streamPipeline(payload);
    }

    // ---------------- Edit pass (2026-10-23) ----------------
    // One change at a time in a marked area of a run's plate. The server crops the area with context, has the image
    // model change it, and pastes back only the area. Versions stay with the run; UNDO steps back.
    let ep = null;   // { runId, size:[w,h], versions:[], current, box:[x,y,w,h] fractions, label, points:[], compare:{before, after} }
    function epStatus(msg, color) { const el = document.getElementById('ep-status'); if (el) { el.textContent = msg || ''; el.style.color = color || 'var(--text-muted)'; } }
    function epImg(v) { return `${PIPE}/api/runs/${encodeURIComponent(ep.runId)}/edits/image/${v}?t=${Date.now()}`; }
    async function openEditPass() {
      const run = selectedReplayRun();
      if (!run || !run.has_twin) { setReplayStatus('Select a run with a rendered image (a keystone candidate) to edit.', '#ffb74d'); return; }
      try {
        const [r1, r2] = await Promise.all([fetch(`${PIPE}/api/runs/${encodeURIComponent(run.id)}/edits`), fetch(`${PIPE}/api/runs/${encodeURIComponent(run.id)}/edits/points`)]);
        const d = await r1.json(); if (!r1.ok) throw new Error(d.detail || `HTTP ${r1.status}`);
        const p = r2.ok ? await r2.json() : { points: [] };
        ep = { runId: run.id, label: runLabel(run), size: d.size || [16, 9], versions: d.versions || [], current: d.current || 0, box: null, boxLabel: '', points: p.points || [], compare: null, restorable: d.restorable || 0, poly: null, draft: null, hover: null };
      } catch (e) { setReplayStatus('Could not open the edit pass: ' + e.message, '#ff5252'); return; }
      if (typeof setFrameMode === 'function') setFrameMode('still');
      const area = document.getElementById('ep-area');
      area.innerHTML = '<option value="drag">Drag a box on the image</option>' +
        ep.points.map((pt, i) => `<option value="${i}">Point ${pt.rank}: ${escHtml(pt.label)} (${escHtml(pt.position)})</option>`).join('');
      document.getElementById('edit-pass').hidden = false;
      epRedoCancel(true);
      epRenderFrame(); epRenderVersions();
      epStatus('Drag a box on the image, or pick a point of interest, then say the change.', '#ffb74d');
      frameHint('Edit pass: drag a box around the area to change. The controls are in the right column.');
      document.getElementById('edit-pass').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    function closeEditPass() {
      document.getElementById('edit-pass').hidden = true;
      frameHint('');
      const runId = ep && ep.runId; ep = null;
      if (runId) document.getElementById('frame').innerHTML = `<img alt="Edited plate" src="${PIPE}/api/runs/${encodeURIComponent(runId)}/edits/image/${(replayRuns.find(r => r.id === runId) || {}).edit_version || 0}?t=${Date.now()}">`;
    }
    function epRenderVersions() {
      const run = replayRuns.find(r => r.id === ep.runId); if (run) run.edit_version = ep.current;
      document.getElementById('ep-ver').textContent = `${ep.label} · showing version ${ep.current}${ep.current ? '' : ' (the original)'}`;
      document.getElementById('ep-versions').innerHTML =
        `<li>The original render ${ep.versions.length ? '<button class="lsa-added-btn" data-back="0" title="Set aside every edit">Back to here</button>' : ''}</li>` +
        ep.versions.map((v, i) => `<li>${escHtml(v.label ? v.label + ': ' : '')}${escHtml(v.instruction)}` +
          (i < ep.versions.length - 1 ? ` <button class="lsa-added-btn" data-back="${v.v}" title="Set aside every later version (files kept)">Back to here</button>` : '') +
          ` <button class="lsa-added-btn" data-redo="${i}" title="Go back to just before this edit, with its box, words and sample filled in">Redo</button></li>`).join('');
      document.querySelectorAll('#ep-versions [data-back]').forEach(b => b.addEventListener('click', () => {
        const to = +b.dataset.back, n = ep.versions.filter(v => v.v > to).length;
        // 2026-10-23: Back to here asks first; two accidental set-asides in one afternoon.
        if (confirm(`Go back to ${to ? 'version ' + to : 'the original'}? This sets aside ${n} later version${n === 1 ? '' : 's'}. The files are kept, and Restore what was set aside brings them back.`)) epRevert(to);
      }));
      document.querySelectorAll('#ep-versions [data-redo]').forEach(b => b.addEventListener('click', () => epRedo(+b.dataset.redo)));
      document.getElementById('ep-undo').disabled = !ep.versions.length;
      document.getElementById('ep-restore').hidden = !ep.restorable;
      if (ep.restorable) document.getElementById('ep-restore').textContent = `Restore what was set aside (${ep.restorable})`;
      if (typeof updateKeystoneUI === 'function') updateKeystoneUI();
    }
    function epRenderFrame() {
      const fr = document.getElementById('frame');
      const [W, H] = ep.size;
      const cmp = ep.compare;
      fr.innerHTML = `<div class="ep-wrap" id="ep-wrap" style="aspect-ratio: ${W} / ${H};">` +
        `<img alt="Current version" src="${epImg(cmp ? cmp.after : ep.current)}">` +
        (cmp ? `<div class="ep-before" id="ep-before" style="clip-path: inset(0 0 0 100%);"><img alt="Before" src="${epImg(cmp.before)}"></div>` +
               `<span class="ep-tag" style="left: 8px;">After: version ${cmp.after}</span><span class="ep-tag" style="right: 8px;">Before: version ${cmp.before}</span>` +
               `<input type="range" class="ep-slider" id="ep-slider" min="0" max="100" value="100" title="Drag to compare before and after">` : '') +
        `<div class="ep-box sample" id="ep-sample-box" hidden><span>Sample</span></div>` +
        `<svg class="ep-poly" id="ep-poly" viewBox="0 0 1000 1000" preserveAspectRatio="none"></svg><div id="ep-dots"></div>` +
        `<div class="ep-box" id="ep-box" hidden><span></span></div></div>`;
      const wrap = document.getElementById('ep-wrap');
      const slider = document.getElementById('ep-slider');
      const panelSlider = document.getElementById('ep-slider-panel');
      document.getElementById('ep-compare').hidden = !cmp;
      // The panel's slider and the frame's slider move the same line between before and after.
      const setCut = val => { const b = document.getElementById('ep-before'); if (b) b.style.clipPath = `inset(0 0 0 ${val}%)`;   // left of the line: the change; right of it: before
                              if (slider) slider.value = val; if (panelSlider) panelSlider.value = val; };
      if (slider) slider.addEventListener('input', () => setCut(slider.value));
      if (panelSlider) { panelSlider.oninput = () => setCut(panelSlider.value); if (cmp) setCut(100); }   // 2026-10-23: opens fully applied; drag left to reveal the before
      let start = null;
      const frac = e => { const r = wrap.getBoundingClientRect(); return [Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1), Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1)]; };
      wrap.addEventListener('mousedown', e => {
        if (e.target === slider) return;
        document.getElementById('ep-area').value = 'drag'; e.preventDefault();
        if (epShape() === 'poly' && !ep.samplePicking) { epPolyClick(frac(e), wrap.getBoundingClientRect()); return; }
        start = frac(e);
      });
      wrap.addEventListener('dblclick', e => { if (epShape() === 'poly' && ep && ep.draft) { epPolyDedupe(wrap.getBoundingClientRect()); epPolyClose(); } });
      window.onmousemove = e => {
        if (ep && ep.draft && epShape() === 'poly') { ep.hover = frac(e); epDrawBox(); return; }
        if (!start || !ep) return;
        const p = frac(e);
        const b = [Math.min(start[0], p[0]), Math.min(start[1], p[1]), Math.abs(p[0] - start[0]), Math.abs(p[1] - start[1])];
        if (ep.samplePicking) ep.sample = b; else { ep.box = b; ep.boxLabel = ''; }
        epDrawBox();
      };
      window.onmouseup = () => {
        if (start && ep && ep.samplePicking) {
          ep.samplePicking = false;
          if (ep.sample && (ep.sample[2] < 0.01 || ep.sample[3] < 0.01)) ep.sample = null;
          document.getElementById('ep-sample-clear').hidden = !ep.sample;
          frameHint(ep.sample ? 'Sample set. Now drag a box around the area to change.' : '');
          epStatus(ep.sample ? 'Sample set: it guides every change until you clear it.' : 'No sample set.', 'var(--accent-cyan)');
          epDrawBox(); start = null; return;
        }
        if (start && ep && ep.box && (ep.box[2] < 0.01 || ep.box[3] < 0.01)) { ep.box = null; epDrawBox(); }
        else if (start && ep && ep.box) frameHint('Area marked. Say the change in the right column, then press Make the change.');
        start = null;
      };
      epDrawBox();
    }
    // Polygon select (2026-10-23): click the corners of a band that runs at an angle; close on the first corner,
    // a double-click or Enter. Only pixels inside it can change.
    const epShape = () => (document.getElementById('ep-shape') || {}).value || 'box';
    function epPolyClick(p, r) {
      if (!ep.draft) { ep.draft = [p]; ep.poly = null; ep.box = null; ep.boxLabel = ''; epDrawBox();
        frameHint('Click the next corner. Close the shape on the first corner, with a double-click, or with Enter. Backspace removes a corner, Esc starts over.'); return; }
      const f = ep.draft[0], near = Math.hypot((p[0] - f[0]) * r.width, (p[1] - f[1]) * r.height) < 10;
      if (near && ep.draft.length >= 3) { epPolyClose(); return; }
      ep.draft.push(p); epDrawBox();
    }
    function epPolyDedupe(r) {
      const out = [];
      ep.draft.forEach(p => { const q = out[out.length - 1]; if (!q || Math.hypot((p[0] - q[0]) * r.width, (p[1] - q[1]) * r.height) >= 6) out.push(p); });
      ep.draft = out;
    }
    function epPolyClose() {
      if (!ep || !ep.draft) return;
      if (ep.draft.length < 3) { epStatus('A polygon needs at least three corners.', '#ff5252'); return; }
      ep.poly = ep.draft; ep.draft = null; ep.hover = null;
      const xs = ep.poly.map(p => p[0]), ys = ep.poly.map(p => p[1]);
      ep.box = [Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
      epDrawBox();
      frameHint('Area marked. Say the change in the right column, then press Make the change.');
      epStatus('Polygon closed. Click on the image to start a new one.', 'var(--accent-cyan)');
    }
    function epDrawPoly() {
      const svg = document.getElementById('ep-poly'), dots = document.getElementById('ep-dots');
      if (!svg || !dots) return;
      const pts = ep.poly || ep.draft;
      if (!pts) { svg.innerHTML = ''; dots.innerHTML = ''; return; }
      const s = a => a.map(p => `${(p[0] * 1000).toFixed(1)},${(p[1] * 1000).toFixed(1)}`).join(' ');
      if (ep.poly) {
        const d = 'M0,0 H1000 V1000 H0 Z M' + ep.poly.map(p => `${p[0] * 1000},${p[1] * 1000}`).join(' L') + ' Z';
        svg.innerHTML = `<path d="${d}" fill="rgba(0,0,0,0.25)" fill-rule="evenodd"/>` +
          `<polygon points="${s(ep.poly)}" fill="none" stroke="#ffb74d" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
        dots.innerHTML = '';
      } else {
        const line = ep.hover ? ep.draft.concat([ep.hover]) : ep.draft;
        svg.innerHTML = `<polyline points="${s(line)}" fill="none" stroke="#ffb74d" stroke-width="2" stroke-dasharray="6 4" vector-effect="non-scaling-stroke"/>`;
        dots.innerHTML = ep.draft.map((p, i) => `<div class="ep-dot${i ? '' : ' first'}" style="left:${p[0] * 100}%;top:${p[1] * 100}%"></div>`).join('');
      }
    }
    document.addEventListener('keydown', e => {
      if (!ep || !ep.draft || epShape() !== 'poly') return;
      if (e.target && /^(TEXTAREA|INPUT|SELECT)$/.test(e.target.tagName)) return;
      if (e.key === 'Enter') { e.preventDefault(); epPolyClose(); }
      else if (e.key === 'Escape') { ep.draft = null; ep.hover = null; epDrawBox(); frameHint('Polygon cleared. Click the first corner.'); }
      else if (e.key === 'Backspace') { e.preventDefault(); ep.draft.pop(); if (!ep.draft.length) ep.draft = null; epDrawBox(); }
    });
    function epDrawBox() {
      epDrawPoly();
      const sb = document.getElementById('ep-sample-box');
      if (sb) { sb.hidden = !ep.sample; if (ep.sample) Object.assign(sb.style, { left: ep.sample[0] * 100 + '%', top: ep.sample[1] * 100 + '%', width: ep.sample[2] * 100 + '%', height: ep.sample[3] * 100 + '%' }); }
      const b = document.getElementById('ep-box'); if (!b) return;
      if (!ep.box || ep.poly) { b.hidden = true; return; }
      b.hidden = false;
      Object.assign(b.style, { left: ep.box[0] * 100 + '%', top: ep.box[1] * 100 + '%', width: ep.box[2] * 100 + '%', height: ep.box[3] * 100 + '%' });
      b.querySelector('span').textContent = ep.boxLabel || 'Area to change';
    }
    async function epRun() {
      if (!ep) return;
      const instruction = document.getElementById('ep-instruction').value.trim();
      if (ep.draft) { epStatus('Close the polygon first: click its first corner, double-click, or press Enter.', '#ff5252'); return; }
      if (!ep.box) { epStatus('Mark the area first: drag a box on the image, or pick a point.', '#ff5252'); return; }
      if (instruction.length < 3) { epStatus('Say the change in a few words first.', '#ff5252'); return; }
      const runId = ep.runId, margin = parseFloat(document.getElementById('ep-margin').value) || 0.6;
      const redo = ep.redoFrom !== undefined && ep.redoFrom !== null && ep.redoFrom !== ep.current ? ep.redoFrom : null;
      document.getElementById('ep-run').disabled = true;
      epStatus('Making the change...', 'var(--accent-cyan)');
      taskStart('Edit pass', 'Changing the marked area of the newest version. Usually 15 to 40 s.');
      try {
        const r = await fetch(`${PIPE}/api/runs/${encodeURIComponent(runId)}/edits`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ box: ep.box, instruction, margin, label: ep.boxLabel || null, sample: ep.sample || null,
                                 edge: document.getElementById('ep-edge').value || 'soft', poly: ep.poly || null,
                                 straighten: !!(document.getElementById('ep-straighten') || {}).checked, from_version: redo }) });
        const d = await r.json(); if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        if (!ep || ep.runId !== runId) return;
        // After a redo the set-aside versions can't simply come back (they would fork the line); their files are kept.
        if (redo !== null) ep.versions = ep.versions.filter(x => x.v <= redo);
        ep.restorable = 0;
        epRedoCancel(true);
        ep.versions.push(d); ep.current = d.v; ep.compare = { before: d.base, after: d.v };
        frameHint('');
        epRenderFrame(); epRenderVersions();
        epStatus(`Version ${d.v} made. Compare with the slider; Keep and continue, or Undo last.`, 'var(--accent-cyan)');
        document.getElementById('ep-keep').hidden = false;
        taskEnd(true, `Version ${d.v}: drag the slider across the image to compare before and after.`);
      } catch (e) { epStatus('The change failed: ' + e.message, '#ff5252'); taskEnd(false, e.message); }
      finally { document.getElementById('ep-run').disabled = false; }
    }
    async function epRevert(to, quiet) {
      if (!ep) return false;
      try {
        const r = await fetch(`${PIPE}/api/runs/${encodeURIComponent(ep.runId)}/edits/revert`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ to }) });
        const d = await r.json(); if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        epRedoCancel(true);
        ep.restorable = ep.versions.filter(v => v.v > to).length;
        ep.versions = ep.versions.filter(v => v.v <= to); ep.current = d.current; ep.compare = null;
        document.getElementById('ep-keep').hidden = true;
        epRenderFrame(); epRenderVersions();
        if (!quiet) epStatus(`Back to version ${ep.current}; ${d.set_aside} later version(s) set aside.`, 'var(--accent-cyan)');
        return true;
      } catch (e) { epStatus('Could not go back: ' + e.message, '#ff5252'); return false; }
    }
    function epRedoCancel(quiet) {
      if (!ep) return;
      const was = ep.redoOf; ep.redoFrom = null; ep.redoOf = null;
      document.getElementById('ep-run').textContent = 'Make the change';
      document.getElementById('ep-redo-cancel').hidden = true;
      if (!quiet && was) epStatus(`Redo of version ${was} cancelled. Nothing was set aside.`, 'var(--accent-cyan)');
    }
    async function epRedo(i) {
      const v = ep && ep.versions[i]; if (!v) return;
      const keep = { box: v.box, instruction: v.instruction, sample: v.sample || null, margin: v.margin, label: v.label || '', edge: v.edge || 'soft',
                     poly: v.poly || null, straighten: v.straighten !== false };
      // 2026-10-23: Redo only fills in. Nothing is set aside until Make the change succeeds (the server does it then).
      ep.redoFrom = v.base; ep.redoOf = v.v;
      document.getElementById('ep-run').textContent = `Make the change (redo of version ${v.v})`;
      document.getElementById('ep-redo-cancel').hidden = false;
      ep.box = keep.box; ep.boxLabel = keep.label; ep.sample = keep.sample; ep.poly = keep.poly; ep.draft = null;
      document.getElementById('ep-shape').value = keep.poly ? 'poly' : 'box';
      document.getElementById('ep-straighten').checked = keep.straighten;
      document.getElementById('ep-straighten-row').hidden = !keep.poly;
      document.getElementById('ep-instruction').value = keep.instruction;
      const mg = document.getElementById('ep-margin'); if (mg && keep.margin) mg.value = String(keep.margin);
      const eg = document.getElementById('ep-edge'); if (eg) eg.value = keep.edge;
      document.getElementById('ep-sample-clear').hidden = !ep.sample;
      epDrawBox();
      const later = ep.versions.filter(x => x.v > v.base).length;
      epStatus(`Redo of version ${v.v}: its box and words are filled in. Nothing is set aside yet. Make the change builds on ${v.base ? 'version ' + v.base : 'the original'}` +
               ` and then sets aside ${later} version${later === 1 ? '' : 's'} (files kept). Mark a new area to cancel.`, '#ffb74d');
      frameHint('Redo: adjust the box or the words, then press Make the change. Nothing changes until you do.');
      epRenderVersions();
    }
    async function epUndo() {
      if (!ep || !ep.versions.length) return;
      try {
        const r = await fetch(`${PIPE}/api/runs/${encodeURIComponent(ep.runId)}/edits/undo`, { method: 'POST' });
        const d = await r.json(); if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        const gone = ep.versions.pop(); ep.current = d.current; ep.compare = null; ep.restorable = 1; epRedoCancel(true);
        document.getElementById('ep-keep').hidden = true;
        epRenderFrame(); epRenderVersions();
        epStatus(`Version ${gone.v} set aside; showing version ${ep.current}.`, 'var(--accent-cyan)');
      } catch (e) { epStatus('Undo failed: ' + e.message, '#ff5252'); }
    }
    document.getElementById('ep-run')?.addEventListener('click', epRun);
    document.getElementById('ep-restore')?.addEventListener('click', async () => {
      if (!ep) return;
      try {
        const r = await fetch(`${PIPE}/api/runs/${encodeURIComponent(ep.runId)}/edits/restore`, { method: 'POST' });
        const d = await r.json(); if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        ep.versions = d.versions; ep.current = d.current; ep.compare = null; ep.restorable = 0;
        document.getElementById('ep-keep').hidden = true;
        epRenderFrame(); epRenderVersions();
        epStatus(`Restored: back to version ${ep.current}.`, 'var(--accent-cyan)');
      } catch (e) { epStatus('Could not restore: ' + e.message, '#ff5252'); }
    });
    document.getElementById('ep-keep')?.addEventListener('click', () => {
      if (!ep) return;
      ep.compare = null; ep.box = null; ep.boxLabel = ''; ep.poly = null; ep.draft = null; epRedoCancel(true);
      document.getElementById('ep-keep').hidden = true;
      document.getElementById('ep-area').value = 'drag';
      epRenderFrame(); epRenderVersions();
      frameHint('Version kept. Drag a box around the next area to change.');
      epStatus(`Version ${ep.current} kept. Mark the next area.`, 'var(--accent-cyan)');
    });
    document.getElementById('ep-sample')?.addEventListener('click', () => {
      if (!ep) return;
      if (ep.compare) document.getElementById('ep-keep').click();
      ep.samplePicking = true;
      frameHint('Drag a box around a correct example, such as a good window, to use as the sample.');
      epStatus('Drag the sample box in the frame.', '#4fc3f7');
    });
    document.getElementById('ep-sample-clear')?.addEventListener('click', () => {
      if (!ep) return;
      ep.sample = null; document.getElementById('ep-sample-clear').hidden = true; epDrawBox();
      epStatus('Sample cleared.', 'var(--accent-cyan)');
    });
    document.getElementById('ep-undo')?.addEventListener('click', epUndo);
    document.getElementById('ep-redo-cancel')?.addEventListener('click', () => epRedoCancel(false));
    document.getElementById('ep-shape')?.addEventListener('change', e => {
      const poly = e.target.value === 'poly';
      document.getElementById('ep-straighten-row').hidden = !poly;
      if (!ep) return;
      ep.box = null; ep.poly = null; ep.draft = null; ep.hover = null; ep.boxLabel = ''; epDrawBox();
      if (poly) { frameHint('Polygon: click the corners of the area along the band. Close on the first corner, with a double-click, or with Enter.');
                  epStatus('Click the corners on the image. Follow the band\'s top and bottom edges.', '#ffb74d'); }
      else { frameHint('Drag a box around the area to change.'); epStatus('Drag a box on the image.', '#ffb74d'); }
    });
    document.getElementById('ep-exit')?.addEventListener('click', closeEditPass);
    document.getElementById('ep-area')?.addEventListener('change', e => {
      if (!ep) return;
      const v = e.target.value;
      if (v === 'drag') { epStatus('Drag a box on the image.', '#ffb74d'); return; }
      const pt = ep.points[+v]; if (!pt) return;
      ep.poly = null; ep.draft = null; document.getElementById('ep-shape').value = 'box'; document.getElementById('ep-straighten-row').hidden = true;
      ep.box = pt.box.slice(); ep.boxLabel = pt.label; epDrawBox();
      epStatus('Box placed around the point. Drag a new box if it needs adjusting.', 'var(--accent-cyan)');
    });

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
        showPoiMarkers(false);
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
        showPoiMarkers(true);
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
