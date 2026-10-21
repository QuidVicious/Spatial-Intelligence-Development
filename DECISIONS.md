# Decision Log: Spatial Intelligence Tool Suite

Design and engineering decisions for Viewfinder (the Cesium and Street View pipeline) and LSA Studio, with the reason for each. Newest first. Status is one of: adopted, planned, open, rejected.

Method: Don designs, sets requirements and tests; Claude writes the code.

---

## 2026-10-21: Round A-1 tested, A-2 started, SI6.3, and the attic storey

**SI6.3 is the default instruction.** Adopted. LSA-Studio/lsa/instructions/SI6.3.md. Changes from SI6.2: the render prompt shows the empty place in positive words (no people, no parked cars, said as what is there rather than as a list of what is not), keeps the permanent fixtures (lamps, railings, bollards), and gives each element words in proportion to its size in the frame. The nb2 addendum matches: rule 5 the empty street with fixtures kept, rule 6 surfaces dry unless the brief's weather says otherwise, rule 8 words in proportion to frame size. The server now picks the highest SI version as the default, so a new instruction does not need a code change.

**Round A-1: delivered and tested.** Files: Dual-Pipeline/domain_engine.py, Dual-Pipeline/server.py, LSA-Studio/pipeline.js, LSA-Studio/lsa_studio.html, LSA-Studio/lsa_server.py. Tested and confirmed by Don: A1 to A3 (a June pano gave "grey-tan and buff-grey", no weather words, no recount of the basement), A4 (a run stamped while the brief was unlinked), A5 (one GO landed), A6 and A7 (the confirm dialog, checked and cancelled), A10 (the frame caption), A18 (SI6.3 the default), A19 (Load lights up), A20. Not tested on their own: A8, A9, A12.

**Round A-2: first part delivered.** LSA-Studio/pipeline.js and LSA-Studio/lsa_studio.html.
- A11: one progress card in the middle of the frame for Excavate, the weft pass and the Street View check: the step's name, a live seconds count with a pulsing dot, then done or failed with a message. Done closes itself after 8 s; failed stays until OK. Tested on Excavate: "the pulsing dot and second countdown are great b/c I can see it working and not frozen."
- 56 and 57: the editor titles say which text is which (tested).
- 58: GO locks the camera in live mode (tested). 59: the GO status line enlarged, and it says plainly when nothing was locked.
- 53: unsaved preset changes are marked; Load fills the name box; loading over changes asks first (tested).
- The stamp line is rewritten only when its words change, so it can be selected and copied.
- The frame caption reads "LSA image: 21 Oct, 10:48".
- The Street View check report flags warm colour words (honey, golden, gold, ochre, amber, tawny) and says why: usually sunlight in the pano, not the stone. "Gold" also catches real gilding, so a flag is a prompt to look.
- A14: a report marks itself when the scene text has changed since it was made.
- A13: REMOVE takes out the phrase with the word that joined it, repairs the punctuation and the list "and", drops a sentence with nothing left, and shows Was and Now under the item; a sentence that may need a word is marked amber.
Open: A15 to A17. Reports from a previous run can stay on screen after switching runs and be marked stale; harmless but misleading.

**The attic storey is a floor, not roof.** Planned for SI6.4 (Round B). Don's definition: in late Georgian Edinburgh the attic storey (parapet attic, wall-head attic) rises straight up past the main cornice in the wall face, with standard rectangular windows lined up with the floors below, to keep the facade's symmetry; a blocking course or parapet at the top hides the sloping roof behind. The model files "attic" under the roof and drops it or turns it into dormers (SI6.1's "three floors plus attic dormers"; today's LSA picture with three floors above the street).
Don's concern: the Georgian wording is location-specific and would push other places (Santa Fe) where it should not. So the instruction carries only the neutral rule: "A top floor whose windows sit in the wall face is counted, whatever it is called; only windows in a roof slope (dormers) belong to the roof." The Georgian terms (main cornice, blocking course, attic storey) go to the place primer, not the instruction.
Idea from Don, to scope: a location preview that sets the system's defaults to the local norms of the place (building types, counts, materials, terms) before the first run; part of the place primer.

**Afternoon: fixtures and storeys in the weft pass.** Tested, no effect yet. Dual-Pipeline/domain_engine.py: the weft pass instruction had no place for street furniture, so the model set lamps aside as "non-structural clutter" while the capture rule keeps "fixed streetlamps"; a PERMANENT FIXTURES section now names them (confirmed from the layout or capture, proposed from the analysis, transient things out). The STOREYS rule now counts a top floor in the wall face, says what is above it (a cornice, a parapet, and whether the roof shows behind it), and assigns each roof form to its building. First test: lamps still left out as unconfirmed, one roof sentence for all, the layout's "flush" kept (USER_SESSION_1.md, 64). Next: a proposed fixture is added as proposed whether or not the capture shows it (thin poles barely show), and the director decides.
Decision: the layout is the lever. What the director has confirmed goes into the layout, because the passes treat the layout as confirmed and their proposals change from run to run (62).

**Corrections and facts from Don, 2026-10-21.** The camera stands in the eastbound lane, left of the street's centre; the street runs forward and curves gently to the right. "Curve gently to the left" in the preset was wrong, Claude's wording from 2026-10-20, never corrected in the preset. The corner block is the end of the terrace, joined to both terraces; no dormers; a parapet with the slate roof showing behind it. The Abercromby Place facade has eleven three-bay houses, some four storeys with a parapet attic, most three with dormer attics; the six distant houses at Dublin Street have dormers. "Tenement" is kept out: outside Scotland it suggests something else. Rust staining ("ochre") on masonry and railings is real and stays.

**The arch under the platts: an LSA proposal confirmed by evidence.** The weft pass proposed "segmental arched" platts from the LSA analysis; Don, who had not noticed it in eight months of study, confirmed it in Street View. The confirmation route working as designed: the model proposes, outside evidence decides.

**Layout lessons (finding 52).** Word count is weight: the subject gets the most words, distant elements the fewest, and anything the user wants drawn must be named. "Flush with the facade" describes a surface, not a count; give counts as counts ("four floors of windows above the pavement"). The preset's "curve gently to the left" was wrong (see the corrections above).

## 2026-10-20: Mapillary as a second evidence source

**Mapillary is evaluated and planned as an evidence source beside Street View.** Planned, after the UI rebuild. Don walked Abercromby Place, Nelson Street and Drummond Place in its viewer. What it adds, from the API documentation: images at 2048 px or full size (Street View gives 640 px); dense, often on-foot sequences with corrected position and heading, so the tool can pick the image nearest the camera or best facing the subject; a capture date per image (choose winter or overcast for colour); detected street furniture with position, facing and first and last seen dates (the place primer's present-day layer, with permanence built in); a reconstructed point cloud and mesh per cluster (sparse, but enough for the ground's trend, such as a slope); faces and plates blurred. MapillaryJS can render a 3D model inside the street imagery, the display end of historical resurrection.
Limits: coverage and quality are uneven (volunteer imagery), so it is one source among several; other users' images are CC BY-SA, so a render that takes one as a direct input may have to be CC BY-SA too (keystones stay text-only); the terms list the permitted commercial uses (developing products, maps and datasets; services for clients) and forbid unapproved data mining; the Mapillary logo and a link go wherever its data is used; Meta owns the service. It replaces Street View only: the frame still comes from Google's 3D tiles through Cesium.

**The rebuilt pano card becomes a source-neutral evidence card.** Adopted for the rebuild. Each evidence item carries its source (Street View, Mapillary, CC photo), image, position, heading, date, role (read for detail; never copied into the image), licence and attribution, so sources plug in without another redesign.

**Many vantage points make a location model.** Planned. Images gathered from all around a place (the plein-air sketches) are summarised per element, not per view: one record for each building, kerb run, railing, tree group or piece of street furniture, with its position, its description, its sources and its status (confirmed, proposed). The scene text for any camera is then assembled from the records of the elements in frame, which is also the fix for details drifting between neighbouring buildings (user session 1, findings 34, 43 and 46). The records are JSON, reusable for other purposes. Open question: a record set derived from CC BY-SA images may itself have to be shared under CC BY-SA.

**Presentation.** The prototype is built and shown where coverage is dense (Edinburgh and many other cities), and says so. Sparse places are named as the open problem rather than hidden.

**SI6.0 to SI6.2: three test runs, same brief and view.** SI6.2 adopted as the default instruction.
- SI6.0: the structure worked (Elements in view; storeys counted above the street, basements apart; no honey). But weather and season words stayed in the element entries, it invented sun when the brief gave no weather, Nelson Street's drop was lost, and wrong claims were tagged [known] (hexagonal lanterns; "Peterhead or Aberdeen granite [known]").
- SI6.1 (weather and season kept to their own section; flat overcast when no weather is given; [known] must name its source): the light rule held and the slope came back, but asked for sources the model invented them ("three floors plus attic dormers [known: listed-building record]" for a four-storey building with a flush attic; "[known: statutory road drainage]").
- SI6.2: the LSA never claims known and never cites a record. Tags are [layout] (the director's own facts), [likely] and [guess]; everything it writes is a proposal, and only the director and street-level evidence confirm. Result: no invented sources, 52 [likely], 7 [layout], the corner building four storeys, Nelson Street falling north. Still: "honey-grey" once in the render prompt, rain and damp words in Stages 2 and 3, a soft veil with gentle shadows instead of none.
Finding: the model cannot tell what it knows from what it has seen often; asking it for a source produces a convincing one. Confirmation comes from outside the model.
Finding: some beliefs survive every wording (Abercromby Place "sloping east" in all three runs; it is level in view). The director's layout is the place to correct them ("Abercromby Pl. is level within the view"), tagged [layout].
The nb2 addendum no longer invites "wetness of surfaces": surfaces are stated dry unless the brief's weather says otherwise. The LSA's own picture has no capture to hold it (the street's curve and the distance came out wrong); holding geometry is the capture's job.

**The saved-view stamp: root cause.** Loading a preset unlinks the brief from the camera (so the preset's facing and lens are not overwritten), and Excavate stamps only when the brief is linked. Every Excavate after a preset load went out unstamped, however often GO was pressed. Confirmed: relinking after the load stamped the run. Fix in Round A (A4): the stamp depends on where the camera is, not on the link.

**Points of interest (B10).** Planned. Up to five ranked markers with the user's own descriptions; the scene section opens with them in rank order (numbers on screen, never in the prompt); each aims its own evidence crop (a plein-air sketch read into words for that element only, shown as a thumbnail first) and marks an edit region and a framing check point. Test with the ranking reversed before trusting it.

**SI6.0, from the session 1 LSA run.** Adopted, to test. LSA-Studio/lsa/instructions/SI6.0.md. Changes from SI3.9: a sixth stage, Elements in view (one entry per element: where, structure, materials, condition; the director's named elements first; storeys counted above the viewer's ground); confidence on every specific claim ([known], [likely], [guess]; SI3.3's recall and reach tags had been lost, and the session run stated unverified kerb granite, "polished" stone and beech trees as fact); materials, structure and condition kept free of weather and light (weathering by its visible result), with light, weather and season in one consistent section of their own (the run had "overcast" and "long diagonal shadows" together); permanent street fixtures as their own entry, transient things named as excluded; a non-masonry example beside the masonry one in Stage 3. Named 6.0, not 4.0: a "System Instruction 4" already existed in July, and the record after the SI5 series said the next major version would be SI6. The output still opens with the JSON block and ends with the render prompt, so the parser is unchanged. The pipeline's domain engine is not affected.

**On-screen names.** Adopted. The Synthesize button becomes CAPTURE ("it reads like tripping a shutter"); the weft pass is shown as "Add LSA synthesis"; the finishing pass as "Street View check". Full list in REBUILD_SPEC.md. Direction for the final visual pass: camera metaphors throughout, the viewport as a view camera's ground-glass plate (the right way up), with a toggleable grid.

## 2026-10-19: Moderated session 1, and the clean set closed

**User session 1.** Done. Don ran the tool as a first-time user from a new saved view to two keystones, Claude moderating; 46 findings in USER_SESSION_1.md (Base), grouped and prioritised. The headline is a quit point: nothing the user had made appeared where he looked, and he concluded he had broken the process. The rebuild spec starts from that file.

**Keystones are made from text only by default.** Adopted. The pano's work ends once it is words. A/B on the same capture, text and seed: the pano image corrected nothing and probably caused the wrong door; text only got the door right. A pano image goes in only when it was taken from where the camera stands.

**Weathering is described by its visible marks, never by the weather that made them.** Adopted, location-neutral. "Rain" anywhere in the scene text pulls the render toward wet surfaces. Every place has a weathering signature (soot crusts here; dust film and streaking on a glass tower; salt bloom in Key West; sun-bleached plaster in Santa Fe), named by its result: pale, cleaner, streaked, crusted, bleached. For the weft pass, the finishing pass and the place primer.

**Finishing pass framing: aim at the subject, about 55 degrees across.** Adopted. Measured: at 55 degrees it placed real details on the right building and found a count to compare; at 105 degrees it added generic details tied to nothing. The pano is read at 640 by 360, so a wide view leaves the subject only a few dozen pixels.

**Colour from overcast panos.** Adopted. "Honey-buff" came back three times today from a June pano lit by summer sun, even though the instruction says light is not surface colour. It also began on the LSA side: the 15 Oct analysis says "pale honey-buff where washed by rain", the colour its own centroid stage rejects. Colour from either side needs the director's check.

**The scene text is written element by element.** Planned. The fresh pipeline text described the scene in general, so the passes had nowhere to attach what they saw, and details drifted between neighbouring buildings (balusters, balconies, a pediment). The director's layout names the main elements; the first text gives each its own sentence.

**The morning's hand-built candidate (10:13).** Held the frame; colour grey-tan; railings in; the bay beside the corner right. Not approved: the corner bay all blind, the return's door arched with sidelights, and Nelson Street rendered flat. The capture's ground at the return is broken mesh, so only words carry the slope, and "steep side street" lost to the model's flat-street default. The framing check measures building edges, not the ground, so a flattened street still reads "held".

**Where the scene text came from (traced).** The hand-built text was layered: the pipeline's base description, Don's structure, one weft pass from the LSA run of 15 Oct 15:37 (Desmococcus olivaceus, West Highland slate, lead-socketed railings, Caithness flags, droved Craigleith; all in that run's analysis.md), the finishing passes, and Claude's edits. The keystone recipe had no weft step; fixed today.

**Corrections to the record.**
- The distant facade on the far right of the Abercromby and Nelson views is the straight end of Abercromby Place at Dublin Street (six three-bay houses in a straight line, by the Gabriel's Road wall and the garden railing), not London Street. Entries of 2026-10-17 and 2026-10-18 that say "London Street" in that sense mean this.
- The street is level in view; the descent begins out of frame where it becomes Albany Street, falling gradually to Broughton Street.
- The garden boundary is a dwarf stone plinth with spearhead railings, like the basement enclosures; the near building's first-floor windows stand on blind balustrades of five balusters.

**Plan.** Prompt round (weathering words, overcast colour, basements not counted as storeys); rebuild spec from the session findings; three rebuild rounds; session 2 with outside testers in early December. After: the edit pass, the place primer with a non-masonry test, a sketch set from CC-licensed photos (Geograph, Wikimedia Commons, Mapillary) for aerial and historical views, and a public privacy statement.

## 2026-10-18 (evening): The clean keystone set at the matched view

**A keystone recipe, written down.** Adopted. KEYSTONE_RECIPE.md (Base): the rule, the two pano jobs, nine steps, the traps hit so far, and the current set for each view. First draft of the step strip for the UI rebuild.

**The clean set at "LSA Alignment: Abercromby and Nelson".** Following the recipe: source run Saturday 2026-10-17 12:00 Synthesize; finishing pass with the 2021 pano (zi3ryjlonoAA8Xl25mFo3g) for London Street and structure, then with the 2025 pano (oQ-PbrZigkImB4CxVEM1tw) for surfaces; Don corrected the first three terrace houses to three floors of windows above the street, the top floor flush, over a basement; keystone with the 2021 pano as reference image, seed 42.
Candidate 16:08: framing held (no measurable change, 4 px). Don: overall good. Faults:
- Two blind windows too many on the return: the corner bay's second floor and the attic of the bay beside it should be glazed. From Don's Street View photo, the return from the corner outward, from the ground up: glazed, blind, glazed, blind; then blind, blind, blind, glazed; the other three bays glazed throughout, the blue door in the middle bay.
- The stone reads too yellow. Don: tan more than yellow, and it varies with the light across Street View dates.
- The near building has no basement railings.
- Still there, and for the edit pass rather than wording (Claude's reading of the render; Don did not flag them this time): arched windows inside the near building's arched recesses, and a lantern instead of the globe-and-cap lamp.
Not yet approved. Next text is in HANDOFF_2026-10-19.md.

**Colour words travel.** Finding.
"Honey-buff" came in with the finishing pass (earlier today it was judged to match Don's photos of the near building) and was then used for the near building, the target building and the terrace. On the render it pushes everything yellow. Next text: "cool grey-tan", named positively ("not yellow" would invite yellow). Rule for the passes and the primer: name stone colour as it looks under flat overcast light, the keystone's light, not as one pano's light shows it.

**Unattached sentences do not land.** Finding.
The railings sentence ("Deep basement lightwells enclosed by ... railings") stood on its own near the end of the text; the model put railings on the target building and the terrace but not on the near building. Fixed by giving the near building its own sentence. Same rule as the weft pass's: attach every feature to the structure it belongs to.

**Confirmed structure was lost between rounds.** Finding; fix planned.
The return's window pattern was in the 2026-10-17 text and in this log, but not in the text the clean set started from, and neither pass put it back (they keep what is there; they do not restore). Claude then recalled the pattern wrongly and dropped half of it until Don's photo matched this log. Fix: confirmed details like the window pattern belong in the Scene layout, which every pass reads, not only in one run's scene text. Same for the five-bay return (still four in the LSA preset).

**The detail crop at a matched pano.** One data point.
The 16:08 candidate went out with "What MAKE KEYSTONE sends" on Detail crop (the default) instead of Full view, by mistake. It held the frame. At a matched pano either setting holds, so far; at a mismatched pano neither did (2026-10-17). The dropdown default is a trap for the UI rebuild.

**A candidate made from a candidate.** Checked in the code.
MAKE KEYSTONE takes only the selected run's capture and camera pose; a candidate carries an exact copy of its source's capture, and the pasted text replaces its scene text. So the render is the same, but the new candidate is filed under the candidate, not beside it. The recipe starts every candidate from the source capture. UI rebuild: "make another candidate" from a candidate uses its source capture.

## 2026-10-18: Finishing pass with the weft rules, auto budget, location-neutral prompts

**The finishing pass follows the weft rules.** Built, tested.
The scene text's structure is confirmed and stays; the pass sets surfaces, names the colours of painted features (doors, frames, shutters, railings, trim) and states opening shapes facade by facade in positive words. It counts bays and storeys on each facade the pano shows and compares them with the text. Anything the pano seems to contradict is reported under "Where the pano seems to disagree (not applied)", never written in; Don decides. Structural additions are listed. A report under the Street View card's status line shows removed, added and disagreements.
Test, B text with "four-bay return" planted: the old pass (2026-10-17) deleted the lamp, the arches and the dormers and turned the building round. The new pass kept all structure, named the royal-blue door, white sashes and black ironwork, corrected the near building's stone to honey-buff with patchy grey soiling (matching Don's photos), added the blind windows' pale buff infill, and on the second run (with the counting step) reported "IMAGE 2 shows five bays on the side-street return; the scene text says four". Without the counting step it missed the planted error. The text still grows about 21% against the 15% asked.

**Removal check on both passes.** Built.
The server compares the text before and after against a list of structural words (counts, openings, elements, materials, render directives) in synonym groups ("squared", "flat-headed", "rectangular" count as one feature), and counts a negated mention ("without dormers") as a removal. It does not depend on the model reporting what it dropped. Tested on the old pass's 2026-10-17 output: it caught the lamp, arches, fanlight, steps, hoods, aprons, storey counts and dormers.

**The weft pass is named in the page.** Section "Weft pass: LSA surfaces", button ADD LSA SURFACES; its list always appears after a pass, removed structure first. Code identifiers keep the old names.

**Auto budget, and a fixed slot for render directives.** Built.
If the scene text and the trees would not fit, the compiler raises the budget to what they need, up to 8000 (the slider's new maximum), and the stepper says so ("budget 6149 raised from 6000 to fit the scene text"). It trims only above 8000, and says so. The slider sets the minimum. "High geometric accuracy: ..." is lifted out before trimming and put back at the end of the scene text, so it is never cut. Don's question that led to it: why make the user set a number the compiler already knows.

**Location-neutral wording in this round's prompts.** Fixed.
Don: Edinburgh-specific wording has leaked into hard code before, and fought against other places (Santa Fe as the example). This round's own prompts had it: the storey rule's example (dormers in a pitched slate roof, basement behind area railings), the position-word examples (the long curved front, the short return down the sloping side street, the terrace), setts and platts as examples of proposed structure, stone-only wording (quarry, soot, crusts), the removal list (Caithness, whinstone), and a British-only street-name check. All made general; the street-name check now also catches forms like Calle de la Vuelta, Paseo de Peralta and Canyon Road. Not yet changed: the domain engine's lenses and the Street View read still lean on masonry ("the local building stone and its quarries", "soot and gypsum crusts", "stone colour, soot or grime"). Planned with the place primer, tested at a non-masonry place against Edinburgh.

**Words-only renders: the frame held 6 of 6 at the old view.** Their limits, at the near building and the return, after rewriting from Don's 2021 Street View photo:
- The near building's ground floor rendered as arched recesses (right) but with arched windows inside them (wrong: flat-headed sashes in arched settings); the corner bay stayed a door (it is a window); triangular pediments appeared over the first-floor windows (they are cornice hoods over small balustrades of five balusters).
- The return's ground floor stayed arched; the lamp stayed a lantern.
These are the model's strongest priors; wording has not moved them in about eight tries. Next: the edit pass.
- The far ground improved: London Street's facades rendered as real buildings where they had been mush behind the trees.

**The edit pass is the next build.** Planned.
Keep a words-only keystone that holds the frame; edit only what is wrong (the corner bay's door to a sash window in its arched recess; the lamp to globe and cap), with a pano crop of that part alone as reference; the composite pastes everything else back, as for prints, so the camera cannot move. First test case: the matched-view keystone's lamp.

**Matched-view keystone, chosen for approval (Don to approve).** The Saturday 13:21 render at "LSA Alignment: Abercromby and Nelson" (full pano ticked, view matched to the pano's heading and pitch, A text, seed 42): framing held (1% zoomed in), surfaces judged very good, only the lamp wrong and distant London Street weak. It had been overlooked in the run list. Keystones belong to their saved view; "Abercromby and Nelson 1" still has the drifted 2026-10-16 15:11 keystone.

**The K key misled.** In the full-screen viewer K shows the view's currently approved keystone, whichever run is selected. With the 9 Oct 13:43 run selected, K showed the drifted Friday keystone, and it looked as if the 13:43 run had shifted. It had not: the 13:43 render and the new 15:25 render both measured on the capture to within 1%. Fix planned: K's caption names the keystone (date, time, framing state).

**A test render used the wrong text without warning.** Selecting a run reloads its own scene text over a pasted one; a render at 15:20 went out with the run's original 1,420 characters. Top item for the UI rebuild: changing the selected run never silently replaces pasted text.

**Place primer.** Planned, after this round.
When an address is entered, the system first excavates the place at coarser scales (city, district, street: the zoom inward, like the old Atget gyre), cached and reused, so a scene at Drummond Place does not spend tokens rediscovering Craigleith sandstone and Auld Reekie's soot. Design rules agreed: a range, not a portrait (what exists across the place and where, not the postcard average, which would strengthen the centroid); layered, nearest layer wins; fed into the centroid stage as the baseline the scene departs from; proposed until Don approves it, after which it becomes a reusable verified layer; cached per place. In Loom terms, the yarn stock.
The present-day layer: street furniture (the international urban-design term: signs, bollards, lamp posts, pay-and-display machines, hydrants, traffic islands) and street utilities (cabinets, wiring, alarm boxes, entry panels). Permanent modern fixtures separate a photograph from a period painting, and the decluttering rule may be removing them with the transient clutter. Transient (cars, people, bins, scaffolding, A-boards) goes; permanent (fixed signs, cabinets, alarm boxes, wiring) stays. The primer supplies what they look like in each place.
Plausibility scale, extended: tourist, city local (someone from Morningside), neighbourhood local (a Feuar).
Pano dates: an older winter pano (Don used March 2021) shows structure and far ground through bare trees; surfaces and colours should come from the newest pano.

**Recorded for the Scene layout:** the target building's return is five bays (Don corrected the record 2026-10-17; the LSA preset still says four until a new LSA run is made).

**UI rebuild list, additions today:** star or flag promising runs and filter to them (the matched-view keystone was overlooked); K names its keystone; never overwrite pasted text on run change; the finishing-pass report placement is fine but the whole status area needs to be prominent.

## 2026-10-17 (afternoon): Pano as words, the detail crop, and the Loom

**The detail crop did not stop the drift.** Tested, rejected as a fix.
Built: MAKE KEYSTONE can send the pano as a crop aimed from the pano at the view's subject (45 degrees across, pitch from the Street View card; pitch 9 fitted the target building from chimney pots to kerb), with its own prompt wording ("a close-up detail... NOT a view of this scene"). B text at the old view, seed 42: drifted 132 px right, 68 px lower, 12% zoomed out, almost the same as the full-pano render. Reading: the camera position is in the subject itself (the angle of its facades, how its lines converge), not only in the street around it, so any photo of the subject from the pano's position carries the car's viewpoint. The crop still helped the surfaces. Kept in the code as an option; not a fix.

**Pano as words: the finishing pass turns the pano into text, and the keystone is rendered with no pano image.** Adopted as the "keep my composition" route.
B structure at the old view, seed 42, budget 6000, no pano image: held 4 of 4 (against 0 of 5 with a pano image, full or cropped). Streets, kerbs and the far end of the street matched the capture well. Surfaces: "all the stuff is there", not the near 1:1 match of the matched-view pano renders. Principle: words have no vantage point.
Limits found, over four renders with the return facade described ever more exactly (from Don's Street View photo):
- The return's ground floor rendered arched every time, with or without the word "arch" (written as "none arched", then only in positive terms: flat-lintelled rectangular openings). The front is arched, and the model arches the whole corner block.
- Counting: blind and glazed windows mostly landed once listed floor by floor, but the top window of the bay beside the corner stayed blind twice.
- The door case grew sidelights until the door was described exactly (plain rectangular door case, rectangular transom glazed in an X pattern).
- Consistently wrong: the corner basement shows a door where there is a window, with no railing (Don has been saving it for a Pro edit session). One render invented a gate in the garden railing.
- Negation does not work in image prompts: "none arched" still mentions arches.

**Finding: the finishing pass rewrites structure from the pano.** Fix planned.
On the B text it deleted the lamp, the near building's arches, steps, hoods and aprons; turned the target building round (called the side-street return five-bay with a transomed door, dropped the arched front); and flattened the terrace to "uniform four-storey houses without dormers". The same problem as the pano image, in words. Its surfaces were good, and it added the moulded eaves cornice with blocking course and the terrace's first-floor cast-iron balconettes (seen in Don's Street View photo). Fix: the finishing pass gets the weft-pass rules (Don's layout is confirmed structure; it writes surfaces, colours of doors and painted features, and opening shapes only) and a removal check.

**Correction to the record: the target building's side-street return is five bays,** door in the centre bay, two bays either side (Don, from Street View). The brief and Scene layout said four; Don to correct the Scene layout. The return, from the ground up: the bay at the corner glazed, blind, glazed, blind; the bay beside it blind on the lower three floors, glazed at the top; all openings flat-lintelled; the door blue, in a plain rectangular case with an X-glazed rectangular transom; the two basement windows right of the steps glazed.

**Next idea: an edit pass on the approved keystone, with the pano for one facade only.** Planned, part of the UI rebuild (the Pro edit session).
Keystone from words (the frame holds), then a targeted edit of the approved plate: "change only the return's ground-floor openings to rectangular; the corner basement door to a window", with a pano crop as the reference for that facade. Prints edit rather than redraw and held the keystone's framing all day, and the composite pastes everything else back, so the pano cannot pull the camera. Untested.

**Budget cap.** Planned.
A 3,709-character scene text trimmed at budget 6000 (the slider's maximum); it was shortened to 3,306 by cutting wording, not facts. Raise the cap above 6000, and keep the geometric-accuracy line in a fixed slot the compiler cannot trim.

**Two user-facing modes for the Street View reference.** Planned (UI rebuild).
"Use the Street View camera": the user accepts Google's viewpoint; the tool helps match the Cesium camera to the pano (a "go to the pano's camera" button); full reference, best surfaces. "Keep my composition": the user's camera rules; the pano reaches the render as words (finishing pass with the weft rules), with the edit pass for details words cannot carry. The alignment check guards both.

**Naming: the LSA Loom.** Adopted.
After Lovelace (1843 Notes): "the Analytical Engine weaves algebraical patterns just as the Jacquard-loom weaves flowers and leaves."
- The LSA Loom: LSA Studio, the whole tool. Public name "the LSA Loom", because "Loom" alone is an existing product name.
- Warp: the structure, set first and never moved: the Cesium frame and the confirmed layout.
- Weft: the LSA's knowledge: surfaces, condition, biology, species.
- Weft pass: what was called the weave or LSA pass. Button label in plain words: ADD LSA SURFACES. Verb: throw the weft, or run the weft pass.
- Pattern cards: the domain keys.
- Cloth: the render.
- Second warp: why a pano image pulls the camera: two structures under tension.
The loom maps onto the bag-and-placement rule of 2026-10-16: the pipeline sets the warp, the LSA throws the weft. Lovelace and Jacquard references can go in public copy; the alt-history fiction around them stays internal, and generated period portraits are labelled as generated.

**Next session, in order:** finishing pass with the weft rules and a removal check; budget cap and a fixed slot for the geometric-accuracy line; weft-pass removal check; rename the weave to the weft pass in code and UI; then the UI rebuild (step strip, gating, test mode, prominent status, the two reference modes, the edit pass).

## 2026-10-17: Alignment check, and what moves the keystone's frame

**Alignment check: each keystone candidate is measured against its capture.** Built.
alignment_engine.py (Dual-Pipeline, numpy and Pillow only) reduces the capture and the plate to edge directions and finds the scale, rotation and shift that best line them up. Shown as "Framing vs capture" under the run list, in the approve dialog's warnings, and after an A/B pair (both arms must hold for a fair comparison). Tolerance, agreed with Don: 30 px, 5% zoom, 1 degree (the 2026-10-16 A arm measured 4% and Don judged it on frame). Cached per run in alignment.json.
Limits: the measurement is weighted by the strongest edges, usually the main building, so "held" means the main structure held; the far end of the street is checked by eye (C in the full-screen viewer). A region-by-region check was tried and was too noisy against the photogrammetry capture.

**Realign makes a new candidate with the plate warped back onto the capture.** Built, of limited use.
The original run is never changed. Only offered when the warped render still covers 96% of the frame. It fixes a whole-frame shift or zoom, not a changed perspective: on the 2026-10-16 keystone the corner building lined up but the terrace still receded at a different angle. A perspective (camera-rotation) warp was tried and did not fix it either. When the model redraws the viewpoint, only a new render fixes it.

**Finding: the Street View reference pulls the render toward its own camera position.** Adopted as the working explanation.
The pano reference was identical on 2026-10-09 and 2026-10-16 except its shape (square then, 16:9 since). Tally, Abercromby and Nelson, seed 42:
- 9 Oct keystone, square pano: held (1 of 1).
- Old view, pano disagreeing with the capture (pitch 10 vs 2.4 degrees, 44 m vs 42 m from the subject): trimmed text 0 of 2 held; A text 1 of 1; B text 0 of 4 (tilted up three times; turned right without the roof phrase).
- New saved view "LSA Alignment: Abercromby and Nelson", angles matched to the pano (heading 60.9, pitch 8.5, FOV 60; pano heading 60, pitch 10, FOV 60), 55.7 m from the subject against the pano's 44.5 m: trimmed text drifted 19% zoomed in (the pano's distance predicts about 25%); full A text with the pano held; full A text without the pano held.
- Old view, B text without the pano: held, where it had failed 4 of 4 with it.
Reading: a pano whose viewpoint disagrees with the capture pulls the framing toward its camera, and a trimmed or different text makes it more likely to win. Small numbers from one location: evidence, not proof.
The pano also carries the surfaces: without it, Don judged the materials clearly worse; with the views matched, patina, soiled blocks and arched versus squared openings were right.
Same pattern as Miller's Row: Google's version of the place overriding the one Don defined. Principle: **Cesium sets the frame; Street View is evidence for detail only.**

**Next: a detail crop for the reference.** Planned.
Send the pano as a tight view of the target facade, with no street, ground or perspective to copy, so it informs surfaces without carrying a camera position. Test against the matched-view renders: it must hold the frame and keep their surface quality.

**Prompt budget default raised to 6000.** Adopted.
A test render at the page's old default (4400) was trimmed without anyone noticing until the settings were read back. Planned: show key settings (budget, seed, pano, text length) in a summary before each render.

**Bus blocking the building: the first real case.** Open.
At the new view, parked cars in the capture hide how the side street drops from the corner, and a Synthesize render drew it flat. In the same frame, cars hide the garden railing and pavement completely, yet they rendered well because the text names them. Text restores hidden objects it names; hidden ground shape needs stronger text or the pano.

**Plausibility scale: tourist versus local.** Adopted as a rating.
Tourist-plausible: convincing to anyone who does not know the corner. Local-accurate: survives the residents who would spot the wrong lamp. Current keystones are tourist-plausible; the globe-and-cap lamp is a local-accuracy marker (a Pro Mode edit to try later).

**UI rebuild notes from this session.** Planned.
Actions must look like buttons (realign was a link). The framing line and other status under the frame are too small to notice: make them prominent, with an action when one applies. Gate controls that can spoil a run (finishing pass, LSA pass) until they are the next sensible step; a test mode that locks text, seed, pano and budget; a step strip showing where you are. A new pano needs UPDATE twice to take typed angles. The pano card starts empty for a new view. A capture needs a full Synthesize with a throwaway render. Run labels are cut off in the dropdown. Earlier: one name per thing, no auto-pick in the LSA dropdown, pasting new text starts a fresh pass, the added-structure box always appears.

**Record gap:** "Fit pano to capture" and the frame outline on the pano preview (2026-10-09, adopted) are not in the current page or in viewfinder.html. Not to be restored as they were: fitting the whole frame makes the reference more of a composition to copy.

**Delivery note:** the second write of pipeline.js and lsa_studio.html this morning silently delivered the first version; caught by checking file sizes. Each delivery is now checked against the expected size.

## 2026-10-16: The LSA join, stage 2, the first A/B, and a new keystone

**The bag and the placement.** Adopted.
LSA Studio is the authority on what the scene contains: materials, condition, biology, species, and named places. The pipeline is the authority on form and position. Street and place names are used on the LSA side (brief, Scene layout, analysis) and translated into position words in the scene text the image model reads. Items in the scene are confirmed (Don's layout or brief, or the capture), proposed (LSA recall only, flagged for Don to keep or remove), or excluded (light, weather and season, set aside for the render stage).
Why: Don's framing. The LSA is meant to know everything in the scene; the pipeline gives each thing its form and place. Proposed items are where LSA finds things Don did not know to look for, so they are shown, not refused. The no-street-names rule was always a rendering rule (the image model cannot map names to pixels), not a public-copy rule.

**The LSA pass sends the LSA run's brief as the director's layout.** Built.
Place, Standpoint, Looking at and Scene layout go to the weave with the analysis. Structure in them is confirmed. Every structural addition comes back with a status (confirmed or proposed) and a source, in an "Added structure: check" list with KEEP and REMOVE; decisions are saved with the run. Render directives and qualifiers in the scene text are kept word for word. Street-like names that survive are flagged.
Why: 2026-10-15's pass refused the dormers and storey counts, which were real, because they were in Don's layout but not the scene text. The weave could not tell recalled structure from confirmed structure.

**The LSA pass dropdown lists runs with an analysis, and previews the chosen run.** Built.
It used to hide any run whose settings ever recorded an error. The preview shows the run's image, time, view stamp and the start of its layout.
Why: the wrong LSA run (2026-10-12 16:48) was woven twice, once on each day, because runs could only be told apart by name.

**Terminology.** Scene text: the pipeline's description of the view, edited in the box under the frame (the LSA pass edits it; "woven text" is the scene text after a pass). Render prompt: LSA Studio's own prompt for its image. Scene layout: Don's description of the view in LSA Studio's brief. The scene text reaches the image model only through the prompt compiler.

**Finding: the prompt compiler trims the scene text.** Adopted: budget raised to 6,000 for these tests.
It reserves the task header and light block, gives the trees a share, and gives the scene text the rest, trimmed at a sentence boundary. At budget 4,400 that was about 1,960 characters; a 2,785-character scene text lost everything after the side-street sentence (terrace, storeys, dormers, railings, kerbs, trees, the geometric accuracy line). Only the TRIMMED flag in the stepper shows it. The 2026-10-09 keystone's 1,532-character text was probably not trimmed. Planned: make trimming impossible to miss, and keep the geometric accuracy line out of the trimmable text.

**Finding: the weave drops structure despite the keep rule.** Planned fix: a removal check.
Both of today's passes dropped or changed structure and qualifiers (droved ashlar, string courses, "like the basements", granite kerbs swapped for whinstone, "four-storey" on the corner block). The added-structure list cannot catch this because it only tracks additions. Fix: structural terms in the input but missing from the output are listed as "Removed: check". The same inputs gave a different weave on a second run.

**Finding: elements the capture cannot show lead the model to rebuild geometry.** Open.
The globe-and-cap lamp, the entrance steps, window hoods and aprons on the near corner building were described by position. The model turned the near facade toward the camera to show them (a false corner). The lamp rendered as a lantern in every render: the centroid won against the text. Next lever: a Street View pano framed to show the globe and cap. Two lamp types in the Moray Feu: the Victorian globe and cap here, and an early 20th-century type that looks art deco (Great Stuart Street, Randolph Crescent). The gas-era history is Don's research; it needs a source before it goes public.

**LSA A/B, first run: inconclusive.** Abercromby and Nelson 1, LSA run 2026-10-15 15:37, seed 42, budget 6,000, same pano, no finishing pass.
A: the keystone's scene text with the structure corrected by hand (storeys, dormers, both corner buildings, the lamp), 2,578 characters. B: A plus exactly what the LSA pass added, nothing removed, 2,785 characters (corrected by hand because the weave dropped structure). No trimming in either.
A held the capture's frame. B tilted up. Re-rendered with the same text and seed, B tilted the same way. With "dark blue-grey West Highland slate roofs" removed, B turned right instead. The 2026-10-09 keystone matches its capture.
Finding: framing depends on the exact scene text plus the seed. Any text change can move the camera, so A/B comparisons need an alignment check before surfaces can be compared. Planned: measure each keystone's shift against the capture and warn before approving a drifted one.
Don's assessment: all of the day's LSA-infused keystones (with the pano) were good; surfaces and materials look almost exactly like the real street, and apart from the streetlight a local could take them for photographs. B without the roof phrase had more and better detail than most renders so far (one render, frame moved). The LSA's share is not separated from the structural corrections and the pano yet.
The target building's blue door (side-street return, 2025-06 pano) appeared in only some renders. It goes into the scene text and Scene layout as a confirmed detail, dated.

**New keystone approved.** Adopted.
B without the roof phrase (seed 42) replaces the 2026-10-09 13:43 keystone for Abercromby and Nelson 1. It is turned right relative to the capture, so prints use it with Sun and shadows off. The old keystone can be re-approved for tests that need the capture-aligned baseline.

**Prints from the new keystone: very good.** Rain, sun, snow and fog, autumn into winter.
One early print grew young trees on the distant lamp columns: the canopy rule ("apply to every tree... leave none bare") read thin poles as trunks. Planned: the canopy rule names lamp columns, posts and railings as not trees.

**Next round, in order:** alignment check; UI overhaul (one name per thing, a numbered A/B panel showing each step); weave removal check; small fixes (no auto-pick in the LSA dropdown, pasting new text starts a fresh pass, the added-structure box always appears, lamp columns are not trees).

**Workflow:** from 2026-10-17 this chat is linked to Don's computer through the Claude desktop app, with access to this folder. Claude writes files in place; Don commits before and after each round.

## 2026-10-15: The LSA join, stage 1: the LSA pass and A/B keystones

**The LSA pass: an LSA Studio analysis woven into a pipeline run's scene text, as a step you run and review.** Built, to test.
A button in the Runs and keystones card takes the scene text in the editor and an LSA run's whole analysis, and returns the scene text with the analysis's materials, condition and biology attached to the elements they describe. Structure stays the scene text's ("SI3.8 paints, the domain engine builds"). Detail is set by distance as judged from the capture image (an approximation: the plan's per-element depth is not built). Left out: light, weather, season, time, compass aspects (turned into exposure terms), street names, numbers and recalled structure. What was left out is returned and kept with the run ("set aside" and "not added"), so LSA's light knowledge is not discarded. UNDO restores the text. Words that should not have survived (sun, shadow, west-facing and so on) are flagged in the status line.
Why a reviewable step: Don can read what LSA added before spending a render, as with the finishing pass. The whole analysis is passed because SI3.9 has no fixed sections after its JSON block.

**Species from the pass go into the run's ecology record as well as its scene text, listed as "to verify".** Built.
Why: date plates and series age the species in the ecology record (2026-10-09). A changed species list makes a new phenology calendar for that keystone.

**LSA runs are stamped with the saved view when made with the Cesium camera linked and sitting on it.** Built.
The pass picks the newest LSA run stamped with the selected run's view; any LSA run can be picked by hand. Runs made before today carry no stamp.

**A/B keystones: one button makes two keystone candidates from the same run, same seed, same pano: A from the text before the LSA pass, B from the text after.** Built.
Both are recorded as a pair (pair id, arm, seed, LSA run) and labelled "A/B A" and "A/B B (LSA)"; each links to the other. Warns if the finishing pass ran after the LSA pass (then only B has had it).

**Finding to keep in mind when reading the A/B:** the pipeline's domain engine is already "lsa-merge-1" (five lenses, centroid, synergy). The test compares that compressed method with SI3.9's full excavation, not "no LSA" with "LSA".

**Test protocol, first run.** Abercromby Place, the LSA run "Nelson at Abercromby" (2026-10-12). No finishing pass in either arm, because the finishing pass rewrites condition from the pano and would overwrite what the LSA pass adds. Same pano reference in both. Two seeds.

**Brief corrections from reading that LSA run.** The saved layout says the garden railing is on the left; it is on the right (SI3.8 caught and resolved it in Stage 4). "Nelson St slopes at roughly 15 degrees" went in as fact and the model built structure on it (stepped string courses); Don confirms it is steep, but the number is unmeasured.

**Later, Don's idea:** use the set-aside light knowledge when the render prompt is synthesized, with LSA writing for the same date, time and light control the pipeline side uses. Not now.

## 2026-10-15: Date plate test, time of day, open light issues

**Keystone > date plate > hour print: works.** Tested 15 June at St Andrew Square (looking north at the Melville column, as a sundial) and at the Washington Monument (1420 Independence Ave, Washington DC, mid June).
St Andrew Square: light on the correct side at 8, 9, 10 and 11 am and 2, 3, 4:25 pm. Washington Monument: correct at [hours tested].
Leaves across hours of one date: held across hour-to-hour runs with no serious drift (provisional, testing continues).
Finding: the shadow mask overcomes the tiles' baked south-east light when the mask is clean. The model still keeps the seed's light; the mask changes what that light is.

**First test invalid: the strip's date was 15 October, not 15 June.** The page sets the date to today on load and when the Live clock is unticked, with nothing to show it. The 8:00 and 16:00 "June" prints and their date plate were October (16 degrees sun, yellowing leaves). Polish pass: make the date reset visible, or stop resetting it on load.

**Open: light on the wrong side around 16:00 at St Andrew Square.** Prompt and Cesium shadows both correct (sun behind the camera, to the left); the image is usually lit from the right, as in morning. 14:00 and 16:25 are correct. Varies from run to run at the same hour.
Working guess: a weak cue. At 16:00 the column's shadow falls away from the camera and is mostly hidden, so the mask says little, and nothing shades the column's right face; the baked light wins. Not checked: whether good and bad masks at the same hour differ, with a fixed seed.

**Open: ghost geometry around noon after several consecutive prints.** A pale faceted copy of the column beside the real one, grey facets behind the trees, dark streaks across the lawn: Cesium mesh shapes darkened into the plate by the mask and painted as objects. The mask only darkens, so the ghost against the sky means the shadow renders and the plate were not registered (about 40 px).
Candidate causes: tiles not fully loaded when a render is taken (the loaded flag can carry over from the previous view), or a field of view mismatch (views are matched by position and angles, not FOV). Noon-specific or cumulative: not separated yet (test: reload, print 12:00 first).
Planned fix: wait until tiles are stable for several frames after each camera jump and shadow toggle; save shadow_base.jpg and shadow_pass.jpg with the run; skip shadows, with the reason logged, when the base render does not match the keystone's capture or the shadow render is brighter than the base anywhere.

**Hypothesis, untested: the problems are specific to the saved St Andrew Square view** (its tiles, its baked light, or high latitude). Washington ran clean, but it differs in latitude, sun height, view and tiles at once, so it does not separate these. Test: a second view from another side of the square.

All three open items move to the clean-up and bug-fix pass. Next: the LSA join.

## 2026-10-14: Keystone, date plate, hour print

**Three layers for prints: keystone (structure) > date plate (the canopy for one date) > hour print (the light).** Built, to test.
Why: leaves changed between hours of the same day, as different growth, not a breeze. Every print regrew the canopy from the bare keystone (Make keystone always renders midwinter noon overcast, so a keystone made from a June run is bare too), with no fixed seed, and the canopy composite only protects what lies outside the trees. Sun shadows made it more visible, since each hour now starts from a different seed image.
- Keystone: unchanged, bare midwinter overcast, so it shows what is behind the trees.
- Date plate: the keystone plus that date's canopy, rendered under the keystone's own neutral light (12:00 overcast), made automatically the first time a date is printed, then reused. Registered in date_plates.json by view, keystone and date; approving a new keystone starts fresh plates. "Remake the date plate for this date" replaces one.
- Hour print: starts from the date plate; its prompt changes only the light and weather ("every leaf stays as in the plate"); sun shadows apply here.
Series make any missing date plate on the server before the frame. With the live clock (no set date), prints keep the original behaviour (canopy and light together).
Don's choice: the keystone stays bare; the "June keystone" he wanted is the June date plate.

**UI round, planned (Don, 2026-10-14):**
- One pinned cluster in workflow order: Synthesize, Make keystone, Replay, Approve as keystone, Print from keystone. Outline and text colour only. States: green = the next decision; dim yellow = in play (already run, can be run again); dark = not available yet. Start: only Synthesize green. After Synthesize: Synthesize yellow, Make keystone and Replay green. After a keystone is made: Approve green. After approval: Print green.
- Approve asks first when the run was not made with Make keystone ("may carry its own light and weather into every print").
- Whole UI from dark grey to full black.
- Street View card: when a pano is loaded, Update and Finishing pass are green; once the finishing pass has run, it turns yellow (in play); clear feedback while it runs, which is now easy to miss.

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
Result 2026-10-13 (Don): St Andrew Square, 9 am and 4 pm, light on the correct side in both. To confirm: a run of four at the same settings, and another view (Leven St, looking south, 10 am). The delight stage takes longer with the switch on because the shadow step runs inside it (mostly the median filter on the mask).

**Sun shadows from Cesium, step 2: prints from a keystone.** Built, opt-in, to test.
With "Sun and shadows" ticked, Print from keystone renders the keystone's saved view in Cesium at the print's date and time, without and with shadows, then restores the camera; the server lays the shadow mask onto the keystone plate and adds the keep-the-shadows rule to the print prompt. If a canopy composite applies, it pastes back the shadowed plate. Skipped, with a note, on the live clock or when the saved view is missing.
Both steps now add shadows only with direct sun: an overcast, foggy, rainy, snowy, twilight or night frame gets none, even with the switch on (this also tightens step 1).
Not covered yet: series prints, which the server runs frame by frame without the browser, so no Cesium shadow pass. Next: render one shadow pair per frame in the browser before the series starts.

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
