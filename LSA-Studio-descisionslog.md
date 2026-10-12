# Decision Log: Spatial Intelligence Tool Suite

Design and engineering decisions for Viewfinder (the Cesium and Street View pipeline) and LSA Studio, with the reason for each. Newest first. Status is one of: adopted, planned, open, rejected.

Method: Don designs, sets requirements and tests; Claude writes the code.

---

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
