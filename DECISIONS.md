# Decision Log: Spatial Intelligence Tool Suite

Design and engineering decisions for Viewfinder (the Cesium and Street View pipeline) and LSA Studio, with the reason for each. Newest first. Status is one of: adopted, planned, open, rejected.

Method: Don designs, sets requirements and tests; Claude writes the code.

---

## 2026-10-09: Storm demo and weather ramps (planning)

**The demo is a storm built on keystone plates: a fixed camera first, a moving camera later.** Adopted.
A fixed-camera weather ramp is doable with the tools as they stand; World Labs Atlas (announced 2026-09-01, camera paths as input, up to a minute of consistent 1440p video, early access only) is the natural engine for the moving-camera half, with keystone plates as its images and the Cesium camera as its path.
Why: a showable demo in autumn, while hiring is still open, beats a better one in the new year. The LSA detail is what makes it more than "an image model reweathering a capture", so the SI3.8 join comes before the storm series.

**Order: an Edinburgh gale at Abercromby first (to be confirmed: Stockbridge or Abercromby), then the Key West hurricane.** Planned.
Why: the gale proves the new ramp where the keystone, pano and Pro Mode text already work. Key West has only an LSA Studio test so far and needs its own saved view, capture, pano and keystone. The hurricane is the reel: the strongest visceral read.

**Weather ramps: LSA drafts the keyframes for each location; Pro Mode is the director's override.** Adopted.
A storm is a sequence of states, not one category; and a Key West hurricane, an Edinburgh gale and a Dorset thunderstorm are different weather on different surfaces, not one ramp at different strengths. SI3.8 reasons from climate and materials, so it drafts what this storm does to this street; the director edits the beats.

**What the ramp needs that the series maker lacks:** per-frame weather state and per-frame time together (a storm rolls in over an afternoon); the same seed across the series; and a way to hold structure still under heavy weather, since the canopy composite only protects frames whose weather matches the keystone. Test one storm frame against the keystone before building it; if buildings drift, lock structure by masking buildings rather than trees.

**Later: era as a third control, and a Hardy engine (walking into the novel, down to the Pure Drop).** Planned for next month.
Era collides with "the capture is the survey" (the capture shows tarmac and wire fences), so it belongs with the historic mode (Bellevue House), with structure traced to records rather than recalled.

## 2026-10-09: SI3.8 join, design agreed (to build after A/B mode)

**Order to SI3.8: confirm the capture frame and fit, fix the finishing pass, A/B mode, the SI3.8 join (off by default), then the first A/B test (control vs SI3.8, two seeds).** Adopted.
Candidate panos, multi-view references and the full gated keystone session move after it. A/B mode covers the comparison whose bookkeeping failed on 2026-10-07; today's provenance fixes cover much of the rest.

**Which LSA run feeds a keystone: automatic by default, with a dropdown to override in Pro Mode.** Adopted ("automatic for the people").
An LSA run made while the camera is linked at a saved view is stamped with that view; a keystone uses the newest LSA run from its own view. The dropdown lists the LSA runs for picking a particular focus by hand. Why: there is one SI3.8 but many LSA runs, each with its own standpoint, facing, focus and analysis; texture from a run facing elsewhere or focused on bark paints surfaces the keystone does not show.

**SI3.8 paints, the domain engine builds.** Adopted.
The domain engine keeps structure tied to the capture (storeys, windows, what is in frame); SI3.8 supplies surfaces, materials and biology: chemical weathering, lichen, patina, rust under cracking paint. That detail is the point of LSA. Time of day, weather, season, and SI3.8's own render prompt (camera and lens wording) are left out.

**Detail by distance, like LOD in a game engine.** Adopted.
Each element gets the detail its distance from the camera can show: near elements the full detail, mid-distance colour, staining and where soiling gathers, far elements overall tone in a few words. The capture's depth gives each element's distance. Why: at 2K a railing 40 m away is a few pixels; text spent on detail that can't be painted is wasted, and on 2026-10-07 it cost the railing. Don't spend polys on a distant rock face the player never reaches.
The prompt budget is the open limit: the first A/B test shows how much detail fits before the renderer drops an element.

**Species carry over from SI3.8, marked "to verify" until confirmed.** Adopted.
Why: species drives the surface reasoning; fissured versus smooth bark changes where moss, lichen and moisture collect. The join writes species into the keystone's ecology record as well as its scene text, because the seasonal series takes species from the ecology record; otherwise a keystone could show one tree while its series ages another. Confirmation comes from the pano or the Moray Feu Association's list.

## 2026-10-09: The capture's frame on the pano, and Fit pano to capture

**The Street View preview shows what the capture frames: grey outside it, a dashed frame line, and solid corner marks.** Adopted.
Cesium is put briefly at the run's saved view (the capture camera, behind the still image), finds the 3D surface points along the four edges of the frame, and projects each into the pano from the pano's position (ground plus about 2.5 m), heading, pitch and FOV. It redraws when the pano settings change.
Why: framing rule, check the corners. If what the viewfinder shows and what gets exposed disagree, composition is guesswork. The live Cesium view and the capture already agree corner to corner (both 16:9, same FOV); the pano is the one from another place, and it showed steps and a window the keystone does not contain.
It is an outline, not a rectangle: the two cameras stand in different places, so nearer things shift more than farther ones. It is exact where it touches surfaces, follows direction where an edge looks at sky, and the note says which corners fall outside the pano, if part of the frame is behind the pano camera, and if the saved view was re-saved after the run.

**Fit pano to capture: aims the pano at the frame's centre and widens it until all of the frame fits, with a small margin.** Adopted.
Why: the reference then spends its pixels on what the keystone shows. If the frame needs more than the API's 120° from that pano, it fits to 120° and says the edges are still cut; a pano farther back would fit it. Fitted settings are recorded as fitted, not as a Maps link.

**Guard: if the server sends back a frame of a different shape than was asked for, the card says so in red.** Adopted.
Why: the old server on port 8000 silently sent squares into a 16:9 box.

**Keystone Street View records also keep the pano's position and whether it was fitted.** Adopted.

## 2026-10-09: Run labels and server restarts

**Run labels lead with when the run was made and what it is; scene conditions come after, in brackets; the list is grouped under day headings.** Adopted.
Example: "16:10 · Keystone candidate" or "13:50 · Synthesize (scene 2026-03-12 14:00, rain)". Keystones leave out the scene date, since every keystone renders neutral midwinter. With All runs showing, the view name is added.
Why: the old label put two dates side by side (made-at and scene date), and twice in one session the wrong one was read, once leading to a run being redone that was already right. Same class of trap as the squeezed pano fields.

**The run list carries a `created` time worked out on the server, and is sorted by it.** Adopted.
It reads the archive timestamp in either format, then a stamp in the folder name, then the file's modified time.

**start_server.bat stops the whole process tree on restart (`taskkill /T`).** Adopted.
Why: uvicorn's --reload left worker processes running after restarts (three were found), and they kept answering on port 8000 with the old server code, so a replaced server.py appeared not to take effect.

## 2026-10-09: Stage 3, step 1: Maps link paste and 16:9 Street View

**A Maps link's FOV ("y") is vertical.** Finding, verified at Abercromby Place.
Test: the URL's 75 on a square preview matched the Maps view top to bottom; a square frame has the same angle both ways. The Street View API's FOV is horizontal, so the tool converts: horizontal = 2 x atan(tan(vertical / 2) x 16/9). Maps' default 75 is 107.5° across, about 13 mm on a 36 mm frame. Earlier notes giving 23.46 mm treated 75 as horizontal and were wrong.

**Street View is fetched at 16:9 (640 x 360) for the preview, the finishing pass and the keystone reference.** Adopted.
Why: the square crop hid the sides of the Maps view, so its framing looked wrong and the angles were "corrected" by hand to match it, which put the wrong angles into a keystone. 16:9 matches both Maps and the Cesium capture; it has fewer pixels than the square (640 is the standard API's limit), and facade detail is to come from multi-view references instead.
Keystones record their size. Keystones made before the switch have no size, are shown as the square they were, and say so. A view's remembered pano from before the switch keeps its angles and is shown at 16:9 with a warning to check it. Propose now defaults to Maps' own default view: pitch 0, 107.5° across.

**Paste the whole Maps address; pano ID, heading, pitch and FOV are read from it.** Adopted.
Pano ID runs to the next "!". Pitch is t minus 90 (the thumbnail's pitch has the opposite sign and is ignored). "!2e0" is read as Google imagery and anything else as a user photosphere, which the API can't serve: the tool says a manual screenshot is the only route (to confirm against a real photosphere link). The link is kept with the pano settings and the keystone record; changing an angle by hand marks the settings as no longer matching a link.

**The pano ID gets its own full-width row; heading, pitch and FOV are three labelled fields, with the FOV shown as Maps degrees and lens mm.** Adopted.
Why: the root cause of the 2026-10-09 bad angles. The pano ID box squeezed the three number fields until their values couldn't be read, so they were adjusted blind. Making the side column resizable didn't fix it, because the problem was the row, not the column.

## 2026-10-09: Run selection and keystone provenance (bugs fixed before Stage 3)

**After any pipeline action (Synthesize, Replay, Make keystone, Print), the run it made is selected.** Adopted.
The frame, run selector, thumbnail, scene text, Street View card and Approve button now all point at the same run. If the new run isn't tagged with the view in the filter, the filter switches to All runs and says so. A failed run selects nothing new. Approving keeps the selection.
Why: the old behaviour kept the source run selected while the new plate showed in the frame, so small thumbnails hid which run was active and Approve could hit the source instead of the candidate (a likely route to the 2026-10-07 accidental approval). Whether the logged "selection moves" bug was this mismatch or a real jump couldn't be confirmed from the code.

**Synthesize and Print ask before discarding unsaved hand edits in the scene editor.** Adopted.
Why: they don't use the scene text, and selecting the new run replaces the editor. Replay and Make keystone use the edits, so they don't ask.

**A source run shows the keystones made from it; a keystone shows its source and its pano.** Adopted.
The run label gains a count ("★ 2 keystones"); under the selector, each keystone is a link marked approved, superseded or candidate. A keystone shows "Made from" (a link back), whether its scene text was hand-edited, and the Street View pano it used (ID, date, angles, or that the fetch failed).
Why: the Synthesize run gave no sign of what came from it, and pano settings were only in run_metadata.json.

**Selecting a keystone shows the pano it was made with, not the view's latest pano.** Adopted.
It is shown without changing the view's remembered pano; "use these pano settings" makes it the view's current pano for the next keystone.
Why: showing the view's latest pano beside an older keystone implied that pano was used.

**server.py: one additive field in the run list (`streetview`, from the run's settings).** Adopted.
Viewfinder ignores it; no other change on port 8000.

**Known gap, for the gated keystone session:** going back to a source run loads its original scene text, so a second candidate made from the source loses earlier hand edits. Making further candidates from the first candidate keeps them.

## 2026-10-09: Pro Mode and the scene editor

**Pro Mode: a user who knows the place may correct the scene text by hand.** Adopted.
Automatic runs test what the tool can find; Pro Mode lets an expert correct it (for example, arched ground-floor openings on one facade, or a railed plinth instead of a stone garden wall). Hand edits are flagged on screen now and will be recorded with the run in the gated keystone session.
Why: both questions matter, but they must not be confused in the record.

**The scene text editor moves under the frame, above the tabs, with a marker showing whether the text is as saved or edited by hand.** Adopted.
Why: editing a long prompt in a narrow sidebar box was the hardest part of Pro Mode.

**Side columns are resizable by dragging their inner edge; double-click resets.** Adopted.
Why: fields in the right column were too narrow to read.

**The Street View pano is remembered per saved view (ID and angles only, never the image) and restored when any run from that view is selected.** Adopted.
Why: re-entering the pano on every reselect lost settings and caused errors. Storing references is fine under the terms; only the image is never stored.

**Bugs logged for the gated keystone session:** making a keystone moves the run selection; the Synthesize run doesn't show which keystones came from it; the pano settings used for a keystone aren't shown anywhere in the UI (they are recorded in the run's run_metadata.json). Fixed the same day, ahead of Stage 3: see "Run selection and keystone provenance" above.

## 2026-10-09: One location, one camera

**One address box at the top of the strip feeds both sides.** Adopted.
Searching moves the Cesium camera and fills the LSA Place field. Replaces the separate LSA Place entry and the Cesium "Go to place" box.
Why: the two sides had drifted to different places (Abercromby Place in Cesium, Duval Street in LSA) with nothing to show it.

**Place updates only on search and on a saved-view jump, never on every camera move.** Adopted.
Why: following the camera would reverse-geocode on every move, replacing a place name with the nearest house number and overwriting typed text.

**While linked, the Cesium camera drives the LSA facing, lens and distance; Standpoint stays hand-written.** Adopted (moved forward from Stage 5).
Linked by default whenever Cesium is shown; unlinked otherwise, so LSA-only runs keep a free dial. Turning the dial, typing in those fields, or loading a saved LSA shot unlinks; Relink snaps back.
Why: a camera position can't describe a standpoint the way "centre of the street at the Nelson St corner" does, and that wording is what makes LSA's composition right.

## 2026-10-09: Stage 2, Cesium in the combined tool

**Stage 2 brings all of Viewfinder over as it works today, re-homed in the new layout.** Adopted.
Why: the pipeline code needs its replay, keystone and Street View controls on the page anyway, and a working combined tool sooner beats a half-ported one. Stages 3 and 4 then rebuild Street View and the keystone flow in place.

**The pipeline client runs as its own file (pipeline.js) and calls the pipeline server on port 8000 directly; LSA calls stay on 8001.** Adopted.
Why: both servers have /api/runs and /api/config, so each side must address its own server explicitly.

**Cesium sits underneath the still image in the same 16:9 frame; STILL mode covers it.** Adopted.
Why: the viewer always has a real size (no blank-canvas start-up), switching is instant, and in STILL mode the mouse can't reach the camera at all, so an accidental drag is impossible there.

**Framing is saved automatically on every capture, on lock, and on every saved-view jump, and survives a page reload.** Adopted.
Why: the slip happens before saving; this makes Back to framing always have something to return to.

**Date and time are shared: one control in the strip drives both Cesium's sun and the LSA shot. Weather stays two inputs: pipeline weather buttons and a described weather line for LSA.** Adopted.
Why: the pipeline needs a fixed weather category; LSA reads free description. One shared date and time keeps the two sides describing the same moment.

**In LIVE mode the dial is read-only: needle follows the camera, wedge shows the field of view, a green tick marks the subject, a dashed line shows the LSA bearing.** Adopted.
Why: the LSA bearing and the camera heading stay visibly separate until Stage 5 links them.

**Series weather ramp (weather changing per frame, for storm build-ups) added to the plan.** Planned.
Note: heavy weather is a big edit and gets no canopy-composite protection; test one storm frame against the keystone before running a series.

## 2026-10-09: Composition input and Stage 1

**Scene layout field in LSA Studio: a plain-language description of what is where, kept separate from Focus.** Adopted.
Why: at Abercromby Place, adding plain compositional description to the standpoint and subject made the LSA render's layout surprisingly accurate (terrace left, garden railing right, corner block deep midground), where address-only runs got form wrong. Tested at one place only; both test streets are famous and well photographed, so a less-documented street is the harder test.

**The working audience shifts from "anyone with an address" toward a location scout who has looked at the place.** Open.
Why: describing the scene from Maps is what makes the composition right. Decide on purpose rather than drift.

**Stage 1 layout built: conditions strip, pinned primary actions, Series and Synthesis as tabs, frame mode label.** Adopted.
Note: the Cesium pipeline server already accepts calls from other origins, so Stage 0 needed no server change.

**Street View URL extraction, folded into Stage 3, fixes the standalone script's issues.** Planned.
- Read the pano ID up to the next "!" instead of exactly 22 characters, so long photosphere IDs aren't silently cut short.
- Drop the invented CIHM-to-CAMSS conversion; warn that user photospheres can't be served by the Static API instead.
- Read pitch from the "t" value minus 90; never from the thumbnail, which uses the opposite sign.
- Check whether the URL's "y" field of view is vertical or horizontal before converting it to a lens.
Known limit: user photospheres (such as the one needed for the Miller's Row columns test) can't be fetched through the API; a manual screenshot is the only route.

## 2026-10-07: Combined tool and keystone workflow

**LSA Studio becomes the base of the combined tool.** Adopted.
Why: its interface was clearly better than Viewfinder's: the frame is never covered, controls are grouped by purpose, and state is visible.

**Viewfinder stays as it is, frozen as the working fallback.** Adopted.
Why: it works and is familiar. The new tool replaces it only once it can make a keystone end to end. Tagged `viewfinder-frozen`.

**Two services stay separate: LSA Studio on 8001, the Cesium pipeline on 8000. The combined page is served from 8001.** Adopted.
Why: modular tools that can later be strung together; a crash or reload in one doesn't take down the other.

**Layout: left sets the shot, center shows it, right grounds it.** Adopted.
- Left: the LSA shot controls, with the facing dial anchoring the top.
- Center: the frame, never covered by menus. Shows the generated still, or the live Cesium view.
- Right: Cesium, then replay runs and keystones, then Street View, kept together.
- Top strip under the banner: time and solar position, weather, and camera telemetry, always visible.
- Tabs under the frame: render prompt, analysis, prompt sent, instruction, settings, series, synthesis settings.
Why: Viewfinder's long sidebars buried the main buttons and covered the frame; scrolling hunted for controls.

**Primary actions are pinned, never in tabs: Synthesize and Make Keystone at the top of the right column.** Adopted.
Why: actions must always be visible. Settings and reports can live in tabs.

**Framing protection: Lock camera, automatic save of the last framing on every capture, and Back to framing.** Adopted.
Why: accidentally dragging the scene after careful framing, before saving, meant reframing from scratch.

**The center frame is labelled STILL or LIVE CESIUM; the switch sits at the top of the Cesium module.** Adopted.
Why: the dangerous moment is grabbing the frame without knowing which mode it is in.

**Anything being overridden is greyed out and says so.** Adopted.
Example: during keystone steps, the conditions strip shows "keystone uses neutral midwinter", since keystones ignore date, time and weather.
Why: settings that look active but aren't caused confusion.

**One dial, two modes.** Adopted.
LSA mode: the dial is an input. Cesium mode: a live instrument showing camera heading, a field-of-view wedge, a subject tick and a pano tick, with distance and lens below.
Why: one familiar instrument; the pano tick shows at a glance when the Street View reference looks from a very different angle than the keystone.

**Use Cesium camera for shot: one direction only, Cesium to LSA, with LINKED and UNLINKED shown on the dial.** Adopted.
Why: guarantees the LSA analysis describes the view being rendered. The reverse direction could only set the heading, and a half-working button is worse than none.

**Street View: paste the whole Maps URL; ID, heading, pitch and field of view are extracted automatically, with a photosphere warning and the capture date shown.** Adopted.
Why: finding the ID by hand caused repeated errors and stalls.

**Street View candidates: up to 5 panos within 60 m of the subject, each with date and distance.** Adopted, to revisit after use.
Why: the nearest pano isn't always the best one (lighting, angle, year). Usually 2 are compared; some spots need more.

**A keystone is a gated session, not a pile of runs.** Adopted.
Six steps, unlocked in order and locked once done: view and subject, capture, Street View, scene text, candidates, compare and approve. Reopening a step marks everything after it out of date. Runs are named automatically and grouped by session.
Why: on 2026-10-07 a control-versus-test keystone comparison failed through bookkeeping: wrong runs selected, texts pasted by hand, pano state lost on reselect, an accidental approval. The method may have been fine; the process wasn't dependable.

**Approving a new keystone keeps earlier ones, marked superseded.** Adopted.
Why: you can always go back to a previous plate.

**A/B mode: one source, two scene texts, same pano and seed, made and labelled automatically.** Planned.
Why: tests like the 2026-10-07 one need to be one click and impossible to cross.

**LSA texture is not yet imported into keystone text.** Open.
Test result 2026-10-07: inconclusive and not trusted (process errors). Observations: added texture visibly weathered the stone once; bark and lichen detail never showed at street distance, and twice cost the garden railing; with scale-matched texture only, the railing returned but the weathering looked no better than the control.
Working hypothesis: carry only texture visible at the shot's scale; the pano image sets overall stone tone more strongly than text.
Next: rerun under A/B mode, at two seeds, before it becomes a default.

**When weaving texture into scene text, texture attaches to an element and never sits between an element and its anchor.** Adopted as a rule, unproven.
Why: the first test text placed a moss clause between the garden wall and its railing, and the railing disappeared.

**Species from LSA: verify, never discard.** Adopted.
Why: species is what the bark, lichen and ageing reasoning depends on. A wrong species makes all of that reasoning describe a tree that isn't there. Verify against the pano or a locked per-view species list (awaiting the Moray Feu Association's identification).

## 2026-10-03: LSA Studio and the domain lab

**LSA Studio built as its own tool and service, in its own folder beside Dual-Pipeline.** Adopted.
Why: pure LSA runs without Cesium; modular; reloads only when its own files change.

**SI3.8 is never edited by the tool; per-model instructions live in separate addendum files, switched on with a tick box.** Adopted.
Why: keeps runs comparable over time and makes "3.8 alone" versus "3.8 plus model addendum" a fair A/B.

**LSA Studio runs are independent, with no conversation memory.** Adopted.
Why: a test's answer must come from the model's knowledge, not from consistency with an earlier answer. A continuous "walk" mode is planned separately.

**The focus field names what to examine, never what you expect to find.** Adopted.
Why: otherwise the test only measures your own notes coming back.

**Domain lab: runs the real domain engine on a saved run, with an editable instruction file.** Adopted.
Why: test instruction changes exactly as the pipeline would run them, before committing them to code.

## 2026-10-02: Pipeline scene text

**Invent texture, never structure.** Adopted.
Why: recalled ornament (pediments, Corinthian orders, dormers) was consistently wrong; recalled weathering, chemistry and plant life were usually close to true.

**Fabric and condition are separate; condition is described surface first, with actual colours.** Adopted.
Why: "pale buff Craigleith" read first outweighed the soot; "moderate" gives the renderer nothing to paint.

**Renderer text never uses compass directions, street names, or narration of what was removed or corrected.** Adopted.
Why: the renderer can't place compass points; narration spends characters and paints nothing.

**When a detail applies to only part of a building group, the text says which part.** Adopted.
Why: arched openings on the pavilions were generalized to every house.

**Keystones re-delight their source capture at a gentler setting (gamma 0.85, or off).** Adopted.
Why: the original lift brightened broad soot along with shadows, about 20 percent on the Ainslie facades.

## 2026-09-29: Street View reference

**The Street View image, not the notes, places the weathering.** Finding.
Evidence: at Abercromby Place, the same notes with the image placed the soot on the correct corner block; without the image, they didn't.
