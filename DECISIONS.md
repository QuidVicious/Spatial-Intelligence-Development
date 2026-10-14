# Decision Log: Spatial Intelligence Tool Suite

Design and engineering decisions for Viewfinder (the Cesium and Street View pipeline) and LSA Studio, with the reason for each. Newest first. Status is one of: adopted, planned, open, rejected.

Method: Don designs, sets requirements and tests; Claude writes the code.

---

## 2026-10-13: Open issues from testing

**Sun side flips in keystone prints from 9 am on.** Fixed in lighting_engine.py (to confirm in a test).
Leven St looking south at Barclay church: 8 am lit correctly (east side in sun); 9 am twice, 10 and 11 am all flipped (west side lit). Cause: the sun maths were correct, but the wording changed category at 9 am, from "hard raking side-light from camera-left" to "backlighting from ahead of the observer", and the side survived only as "left-facing walls are brightly lit". An image model can read "left-facing walls" as "the walls on the left", which mirrors the light.
Fix: every directive now opens with the lit side of the frame ("Sunlight comes from the LEFT side of the frame; the sun is never on the RIGHT side"), the summary always names the side once the sun is off the view axis, the backlit rim is placed on a named edge, and the lit and shaded surfaces are given with examples that cannot be mirrored: "the left-hand faces of towers, spires and chimneys, and the fronts of buildings along the right-hand side of a street". The compass azimuth was removed from the renderer's directive, in line with the 2026-10-02 rule.

**LSA Studio prompts give no sun position.** Open. The text model must work the sun out from facing and time, which models do unreliably. Planned: the LSA server computes the sun for place, date and time and states it in camera terms.

**Cesium's sun read the time slider as UTC.** Fixed in pipeline.js.
The date and time controls now mean local time at the location, as the lighting engine already read them: the page takes the location's time zone from /api/weather (Open-Meteo), applies daylight saving for the chosen date, and falls back to an offset from longitude until the zone is known or if the weather service fails. Hovering over the time shows which zone is in use.

**The Pipeline result tab showed only the last pipeline action in this browser session,** not the selected run (it showed clear sky on a rainy run). Fixed: the tab now loads the selected run's own prompt from its folder (/api/runs/{id}/prompt finds the text that opens with "[TASK:" in run_metadata.json or the run's text files), with the run's date, time, weather and whether the canopy composite was applied.

**Finding: the image model keeps the light that is in its seed image and does not follow light-direction words.** Confirmed 2026-10-13.
St Andrew Square looking north at the Melville column: prints and a fresh Synthesize at 4 pm all lit the east face, although the prompt said, correctly and plainly, that the sun was behind the camera to the left. Reviewing earlier runs, the light has always come from the south-east; most views faced east, where that looks natural, so it went unnoticed until the south-facing Leven St run. The model does follow sun height (shadows lengthening and warming toward dusk). Likely source of the fixed direction: Google's 3D tiles carry the light of the day their aerial photos were taken, so every capture, and to some degree every keystone made from one, starts with that sun. The Street View reference is not involved (it is sent only when making a keystone, and the St Andrew Square pano is overcast).

**Cesium's sun and shadows were off in this tool:** captures are only Google's tile textures, which carry the light of their aerial photos. Record gap: the Washington Monument sundial tests that passed over a month ago were manual, Cesium and Gemini in AI Studio (Don). What differed from the pipeline is not yet known; first question is whether those Cesium screenshots showed cast shadows. The 2026-10-02 gentler keystone delight affects keystones and prints only, not fresh Synthesize runs, so it does not explain the 4 pm Synthesize failure.
Test switch added to the Cesium card: "Sun and shadows" turns on Cesium's sun for the strip's date and time with cast shadows (tiles are unlit, so expect cast shadows rather than face shading); while on, captures include them.

**Sun shadows from Cesium, step 1: Synthesize.** Built, opt-in, to test.
Cesium's sun and cast shadows checked at St Andrew Square: the column's shadow moves correctly with the hour. A rough first try (Synthesize with Cesium shadows in the capture) came out right once and wrong once at the same settings: the CUDA delight pass, built to strip light and shadow, weakens Cesium's shadows along with the tiles' baked light, and the lighting directive's SHADOW OVERWRITE RULE told the model to erase every shadow in the plate.
Now, only when "Sun and shadows" is ticked at Synthesize: the client captures twice at the same camera and time, without and with Cesium's shadows; the shadowless capture is delighted as usual; the shadow mask (shadowed brightness over shadowless, floored at 0.35) is laid onto the delighted seed after delighting; and the SHADOW OVERWRITE RULE becomes "the cast shadows in the reference plate are correct for this date and time: keep them". The run records sun_shadows (applied, coverage) and saves sun_shadow_mask.png. The run archives its shadow-free capture and seed, so keystones and replays at other hours are not baked with these shadows. With the switch off, nothing changes. Not yet: prints from a keystone (step 2: render the saved view at the print's time and lay its shadows onto the keystone plate).
Test: about four Synthesize runs at the same settings, counting how many put the light on the correct side.

**Planned fix: give the model correctly lit pixels, not words.** Cesium renders the saved view at the frame's date and time with shadows (the time zone fix of 2026-10-13 makes its sun exact). Option B, to test first: use that render's light and shade to pre-light the seed (darken shaded faces, lay in cast shadows) before it is sent, so the model's habit of keeping the seed's light keeps the right light. Option A, fallback: send the render as a second image to match. Needs: a check that Cesium's sun is right at St Andrew Square at 4 pm, and synthesis_engine.py.

**An approved keystone was labelled as an ordinary run.** Fixed in pipeline.js and server.py.
Approve accepts any run, but labels and links recognised a keystone only by the keystone_candidate flag set by Make keystone, so the Leven St keystone (an approved run without the flag) showed as a plain run with a midwinter scene date; K in the viewer found it through keystones.json. Now a run is a keystone if it was made with Make keystone, or is the approved keystone, or was approved earlier and replaced; the server also treats mode KEYSTONE as the flag.

**Tree drift in prints from a keystone.** Open. Trunks and branches change shape between prints. Likely cause: the canopy composite keeps keystone pixels outside the trees, so the trees are redrawn every print (by design, for the seasons) with nothing holding their structure. First things to try: a fixed seed, and an instruction that trunk and branch structure stay unchanged.

**Weather presets on prints:** reported broken, then found working (a missed step). No change.

**New tool, planned: a sequence player and video exporter for public content.** From a folder of time-of-day or seasonal prints: scrub at any speed (like holding an arrow key in the run viewer, which already looks striking), set holds on chosen frames, and export a video for the website. Like the Series tab, but for presentation. It is the tool the planned seasonal montage needs.

## 2026-10-12: Refinement in two phases (from Don's first dock sessions)

**Phase A tunes the brief; phase B finishes on the render prompt.** Adopted, refines the refinement loop entry below.
Phase A: layout and structure (street arc, junction angle, storey counts) are corrected in the scene layout, excavating each time; materials vary with every excavation and are not judged yet. Phase B: once layout and structure are right, the run with the best materials is kept and only its render prompt is edited, so the analysis and the materials stay fixed. The winning layout wording goes back into the brief.
Why: excavating rewrites the analysis and the render prompt every time (materials came and went over three runs); the render prompt path changes only the image.

**Diagnostic: when the image is wrong, check the render prompt.** If it lost or garbled the layout, the fix belongs in the brief; if it has the layout right and the image does not, the fix belongs in the render prompt.

**Measure chance first:** render an unchanged prompt once more to see how much an image varies on its own, before crediting a wording change.

Finding: the dock makes the look, find, correct cycle continuous; three runs gave steadily better results. Brief and render prompt edits work best together.

## 2026-10-12: Lenses shown, JSON hardened, SI3.9, place mode drafted

**LSA Studio shows the lenses SI3.x chose for each run, as soon as the analysis arrives.** Built.
SI3.8 selects 3 to 5 lenses per run and names them in its LSA_METADATA block (the 2026-10-03 garden run chose four, under its own names). The server reads that block, strictly if it parses and loosely if not, saves it with the run, and the page lists the lenses under the message line. Older runs are read from their saved analysis.
Note: the pipeline's domain engine uses five fixed lenses; its progress panel label is stale. That panel is relabelled when SI3.x replaces the engine.

**All JSON reads and writes are hardened.** Built.
LSA server: one helper reads every JSON file and falls back to a default (with a console note) if the file is missing, corrupt or the wrong shape, so one bad run never breaks the runs list; every JSON write is atomic (temporary file, then swap) and checked to read back; models.json errors name the missing key. Pipeline server: its JSON reader now returns objects only. Both pages skip a malformed line from a server stream instead of stopping the run. Not audited: the pipeline's archiver module, which writes run_metadata.json (not in hand).

**SI3.9: SI3.8 with a valid output schema.** Adopted.
SI3.8's schema had an extra closing bracket (`"Domain Key 5"]]`), invalid JSON. SI3.9 fixes it, asks for valid JSON explicitly, shows 3 keys as the example instead of implying always 5, and replaces one em dash. Nothing else changed, so 3.8 and 3.9 runs stay comparable. SI3.8 is kept as is.

**Place mode drafted as an addendum (place_mode_DRAFT.md), for review.** Not yet used.
Realizes a whole address by element, with hidden elements, permanence, confidence, "true as of" for recalled facts, and the moment set aside; one strict JSON object as output.

**Finding: recalled biology can be decades out of date.** The 2026-10-03 garden run named Lecanora conizaeoides, a lichen characteristic of sulphur-polluted cities that declined as air quality improved. Flora is a finer era check than soot: no one cleans the micro-biome of a garden. Recalled condition and biology therefore carry "true as of", and recalled species stay "to verify".

**Finding: the Ainslie Place garden railing is not spearheaded** (Don: a rail that rises, loops over and comes back down). Spearheads were the image model's centroid for New Town railings. The 2026-10-03 render also added a diagonal iron bar across the foreground that does not exist there. Both are what grounding (capture and Street View) must fix, and good first cases for the refinement loop.

## 2026-10-12: One LSA stack and the place model (planning)

**SI3.8 becomes the only domain instruction, for both LSA Studio and the pipeline; the pipeline's separate domain engine is retired after A/B tests show SI3.8 is better.** Planned.
Why: two domain stacks meant two sets of lenses and two places for knowledge to drift (the progress panel already disagreed with the engine). SI3.8 is never edited; grounding rules go in a separate addendum.

**Three steps, each with one job.** Planned.
1. Realize the place: SI3.8 works out everything at the address, not just the shot.
2. Look at the evidence: the capture and Street View show what is there and how it looks today; recall fills in, evidence corrects. Transient and seasonal things are ignored.
3. Focus and paint: choose from the place by what this shot sees, and write the scene for the renderer. Not a clean-up of a photograph: a landscape painter building the real scene in the studio from location sketches and knowledge.
Light comes after: it is cast across the focused scene, not baked into the place.

**Detail by distance and by attention.** The subject gets full detail even in the midground; a near element the shot is not about gets less; distant elements keep their form (fenestration, pane layout) and lose fine texture. The focus field supplies the attention.

**The place model: what an address is, kept once and reused by every shot, keystone and series frame there.** Planned.
Two layers: facts (JSON: geometry, coordinates, materials, species, which house is which) and character (prose: humidity, soot history, drainage behind the vaults, the architect's intent). Organised by element (a house, a tree, a run of railing). Hidden elements are kept but appear only when in view or asked for.

**It grows with every run, under provenance rules.** Each run appends to the elements it saw, and every item carries its source: seen in evidence, recalled, or corrected by Don. Repetition never upgrades a recalled item; only evidence or Don's confirmation does. Disagreements between runs are kept and flagged, never overwritten.

**Place and moment are separate layers.** Leaves on the bark, wet surfaces, mist and sky are the moment, split off before anything enters the place model; they are what the season and weather ramps vary.

**Permanence classes for what Street View shows:** permanent (built into stone or iron: window box brackets and ledges, balconettes, boot scrapers, lamp standards, railings, fanlights), seasonal (planting, foliage, wreaths), transient (cars, bins, scaffolding, signs). The fixing is permanent even when its contents are not. Uncertain items are flagged for Don, not guessed. This records fine structure Cesium cannot resolve. Strong extra signal: a detail present in Street View from different years is almost certainly permanent.

**Next:** read SI3.8.md and Don's example analyses to see how much of step 1 SI3.8 already does, and what steps 2 and 3 must add. Then the place model spec.

## 2026-10-12: Editor dock built

**The dock under the frame replaces the scene text editor and is the one place for long text.** Built.
Sources: standpoint, looking at, scene layout and focus (LSA brief); the render prompt of the open LSA run; the scene text of the selected pipeline run. Clicking a brief field opens it in the dock with the caret there; tabbing into it opens the dock but leaves the caret in the field. The Render prompt tab, or clicking its text, opens the prompt; "Edit this run's scene text below" in the Runs card opens the scene text. Esc or Close closes the dock; with a pipeline run selected it falls back to that run's scene text, as the old editor did.
The dock and the source share one text, so nothing is saved or pasted. Brief fields are marked with a brief-coloured dot; the field being edited is outlined and tagged "Editing below".

**The journey strip shows two methods.** LSA: Brief > Analysis > Render prompt > Image. Pipeline: Capture > Scene text > Plate. Each step has its own colour (brief ochre, render prompt cyan, scene text lavender), always shown with its name.

**Render prompt hand edits are kept apart from the model's text.** Built.
The edit is a draft until rendered; "Render with this text" sends it. The server keeps the model's prompt in render_prompt_model.txt, saves each edited version as render_prompt_vN.txt, and records which prompt made which image in the run's render_log, flagged as edited. Opening another run with an unrendered edit asks first. This is the groundwork for the refinement loop.

## 2026-10-12: Capture frame overlay parked

**The capture frame on the pano and Fit pano to capture are removed from the code until LSA and the Cesium pipeline are fully joined and testing well; they return as a Pro Mode polish item.** Adopted.
The code is kept in PARKED_capture_frame_overlay.md with restore steps. The 16:9 fetch, Maps link paste, readable angle fields and the frame-shape guard stay. Keystone records keep the pano's position.
Why: not critical to the join, and it was the one piece that moved the Cesium camera behind the scenes; fewer moving parts while the join is tested.

## 2026-10-12: LSA refinement loop and an editor dock (planned, after the Cesium join)

**Refinement loop: rate a run, write a correction for what scored low, revise the render prompt, render again; repeat until the image is right.** Adopted.
An iterative session, not one shot. Example: at Abercromby and Nelson St, materials were excellent but the junction rendered as a Y instead of a right angle turning out of view, with only the corner building's Nelson St facade visible.
Why: lets LSA do the heavy lifting so the grounding pass becomes finishing carpentry.

**The correction revises the render prompt; the analysis is kept.** Adopted.
High-scoring aspects are locked and kept word for word; the correction is merged into the prompt with the smallest change, shown as a before and after before rendering. Why: excavating again rewrites the analysis, and the gold (materials that scored high) may not come back.

**Ratings: 1 to 5 with a written anchor for each score, on a small fixed set: layout, structure, materials, condition and weathering, vegetation, light and atmosphere, photographic realism.** Adopted.
Every low score carries a note, and the note is the correction. 1 to 10 is too fine for one rater. Ratings are kept per pass, so a session shows whether it is converging; over many sessions they show where LSA is strong and weak, which tells the grounding pass what it still has to do.

**Pass 1 is the model's finding; later passes are director's corrections, recorded separately.** Adopted.
Why: LSA runs test the model's knowledge, and the focus field never says what to expect. A correction is what to expect, so it gets its own field and the record keeps the two apart, as with Pro Mode.

**Open:** whether the image model accepts a fixed seed (without one, a change between passes mixes the correction's effect with chance; render two per pass instead). Layout may be hard to fix by text alone: cap a session at about five passes and show the score trend.

**Editor dock under the frame: the one place for all long text, instead of a tab per field.** Adopted.
Clicking a long field (scene layout, standpoint, subject, focus, render prompt, the pipeline's scene text) opens it in a large editor under the frame, labelled with what is being edited and where it comes from; the sidebar field highlights and shows "editing below"; both views share one text, so there is no save step. The frame stays in view, since the text is written while looking at the image. The dock later hosts ratings and corrections. The pipeline's scene text editor joins the dock.
Why: editing in small sidebar boxes was hard, another tab would add to a long row, and the Pro Mode editor under the frame already works.

**The dock teaches the method.** Adopted.
A journey strip in the dock header, Brief > Analysis > Render prompt > Image, highlights the step being edited. Each stage has one colour used everywhere (sidebar highlight, dock header, journey strip, tab label), always paired with its name, never colour alone.
Why: users should learn the components and how they fit, until scene layout and render prompt feel like steps in one journey and the balance between them is second nature.

**A hand edit to the render prompt is a Pro Mode edit: marked "edited by hand" and recorded with the run.** Adopted.
Why: the render prompt is the model's output; editing it skips the analysis. Composition is fixed in the brief; the render prompt is touched for finishing.

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

## Background: before this log (January to September 2026)

Recorded 2026-10-12 from Don's account; dates are approximate.

- **Late January 2026:** work with Claude begins: method research and early tools.
- **Early summer:** the two sides of the method, the model's knowledge and real-world grounding, become the central problem. All testing is by hand in Google AI Studio. The tools of the time keep being reframed by what the manual tests show; none is finished, but the method keeps being distilled.
- **Mid-summer:** walks along the Water of Leith, from St Bernard's Well to Dean Bridge and down into the valley, give the method its current form and start the system instruction that becomes SI3.8. Occlusion is first worked on there, and leads to the JSON geometric ground-truth model. Cesium and Google Earth Studio are in use; Street View is discussed but not acted on until the autumn.
- **Through the summer:** the system instruction is rewritten around the strengths and weaknesses of Gemini 3.1 Flash Image (Nano Banana 2), becoming SI3.8, which works better than any tool before it.
- **September:** the manual process collapses under its own complexity. Copying and pasting between AI Studio runs causes more errors than it catches, and the closing gap between the two sides makes the tools still in development obsolete before they can be fixed. Decision: automate from the ground up, with SI3.8 as the benchmark.
- **September to early October:** the dual pipeline is built, grounding side first. It drifts from the method's model knowledge and produces pristine facades that look newly built. Then the first LSA dashboard (LSA Studio, 2026-10-03) produces runs like the Ainslie Place garden test, and the two sides begin to merge.
- **The two-sided design** (brief on the left, grounding on the right, the frame between) took shape in building the tool as much as on the whiteboard.
- **Now (October):** SI3.8 to drive the grounding side too, bringing it back to the method it had drifted from.
