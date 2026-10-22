# User session 1: a first-time run of LSA Studio

2026-10-19, 10:40 to 14:20. Don played a first-time user; Claude moderated and logged. Everything was made fresh: a new saved view ("LSA session 1: Abercromby and Nelson"), a new brief, a new LSA run (11:09), a new capture (Synthesize 11:33), the weft pass, two finishing passes (pano JYFr07JvOuS78jFWLRHPMA, June 2025, at 105 and 55 degrees across), and two keystones (14:08 with the pano image, 14:14 text only), seed 42. Rule for the moderator: the user tries each step from the screen first; every time the moderator has to step in is a finding.

The headline: at finding 10 the user said "This is where, as a tester, I'd quit and hand it all back." Nothing he had made or saved appeared where he looked, and he concluded he had broken the process.

Priority: P1 = blocks or misleads a first-time user; P2 = costs time or trust; P3 = polish. (+) marks something that works and is the model for the fix.

## A. Orientation and flow (the quit point)

| # | Finding | P |
| --- | --- | --- |
| 10 | Quit point: nothing the user made appeared in the dropdowns; he thought he had broken the process and wanted to start over. The step strip must always say where you are, what is next, and where your saved things are. | P1 |
| 9 | Controls for later steps are visible and look usable before they can work (the LSA dropdown before any capture exists). Gate them. | P1 |
| 22 | Everything is on screen at once: the right column runs from the weft report through prints and Street View to an unfiltered list of 68 LSA runs. Show the current step. | P1 |
| 1 | Several places to enter a location (left address and GO, Cesium search, saved view, pano card); none is clearly in charge. The left field "feels almost inconsequential". One place sets the location; the rest follow it. | P1 |
| 2 | The user saved in two places (a saved view on the right, a preset on the left) without knowing which mattered. Saved view, preset and Scene layout have no visible relation. | P1 |
| 3 | "Excavate and render" does two things; the user wanted the LSA text only. | P2 |
| 8 | Saving a view does not make it the current view (only GO does). Excavate should say "this run will be stamped with: [view]" before it runs. | P1 |
| 6 | The LSA run was not stamped with the saved view, and nothing said so. Cause found 2026-10-20: loading a preset unlinks the brief from the camera, and Excavate stamps only when linked (see 49). Workaround: press "Unlinked: relink" after loading. | P1 |
| 44 | After MAKE KEYSTONE the new candidate becomes the selected run, so a second MAKE KEYSTONE silently builds a candidate of a candidate. Keystones always build from the capture. | P1 |
| 12 | "No replayable runs" is jargon. Empty states name the next action: "No capture of this view yet: press Synthesize". | P1 |
| 13 | The viewfinder shows the LSA's own picture with no label; the user took it for a keystone. Label it ("LSA image, not the keystone"). | P2 |

## B. Status and history

| # | Finding | P |
| --- | --- | --- |
| 5 | Excavate and the finishing pass have no prominent running and done state; the user could not tell when they had finished. | P1 |
| 16 | (+) Synthesize's step-by-step progress works. It is the model for Excavate and the passes. | |
| 33 | No way to tell which version of the text is in the box, or whether a pass has run on it. Each pass leaves a history line ("Finishing pass, 13:45, pano JYFr..."). | P1 |
| 30 | The weft report goes stale after a hand edit and still reads as current. Refresh it or mark it ("from the weft pass at 11:41; edited since"). | P2 |
| 41 | The keystone used the pano when the user believed the box was off (clicked more than once, misremembered). The confirm dialog says "with pano" or "text only". | P1 |
| 18 | (+) The preview under the LSA dropdown identifies the run and says "not stamped with a view". Other dropdowns should do the same. | |

## C. Names and language

| # | Finding | P |
| --- | --- | --- |
| 19 | One step, three names: heading "Weft pass: LSA surfaces", button "ADD LSA SURFACES", and "weft pass" in conversation. The screen uses one plain name; "weft" stays internal. | P1 |
| 23 | Proposals use specialist words (rusticated, platts, finials) that even a user who knows the street had to ask about. Each gets a plain gloss or a small picture. | P2 |
| 32 | Each pano's role is explained in plain words where it is used: "read for detail, never copied into the image". | P2 |

## D. Camera and panos

| # | Finding | P |
| --- | --- | --- |
| 14 | The first GO after "Show Cesium in the frame" leaves the camera high in the air; a second GO brings it to the street. Since the start; it taught the user to press GO compulsively. | P2 |
| 11 | Camera drift after GO quietly breaks the saved-view stamp (tolerance 0.5 m and 0.1 degree). | P1 |
| 4 | The user picked a pano by eye from several nearby; the tool should propose the best match for the camera. | P2 |
| 31 | Nothing says how to frame the pano for each job; a new user goes wide. For the finishing pass: aim at the subject, about 55 degrees across (see 37). | P2 |

## E. Reports and review

| # | Finding | P |
| --- | --- | --- |
| 20 | The weft report asks for expert judgement (KEEP or REMOVE "urn finials", put back "rectangular") without showing each item in its sentence or saying what happens by default. | P1 |
| 26 | REMOVE deletes the exact phrase and leaves the sentence broken ("encloses a park edge, with a."; "railings with lead-caulked into"). The warning line is easy to miss. Cut cleanly or rewrite, and show the result. | P1 |
| 27 | "Rain" anywhere in the scene text pulls the render toward wet surfaces. The warning was right but did not say why or what to write instead. Rule: weathering is described by its visible marks, never by the weather that made them (decision, see DECISIONS.md). | P1 |
| 28 | The weft pass swapped a verified tree (wych elm) for an unverified one (beech) and only listed it under "verify". Swaps are changes to approve. | P2 |
| 25 | Anything in the director's layout is marked "confirmed", even a mistake (London Street for the Dublin Street end of Abercromby Place). Nothing checks the director's own names. | P2 |
| 36 | "No disagreements" means nothing when the text states no counts: the finishing pass can only contradict structure the text already states. | P2 |

## F. The scene text (method)

| # | Finding | P |
| --- | --- | --- |
| 34 | The fresh pipeline text describes the scene in general, with no sentence per building, so passes have nowhere to attach what they see. The layout names the main elements; the first text is written element by element. | P1 |
| 43, 46 | Details drift between neighbouring buildings: balusters and iron balconies swapped; a balustrade and a triangular pediment appeared on the target building. | P1 |
| 24 | Structure the user knows does not get in unless written into the layout (the balusters). The layout field prompts: "What do you know about the windows, doors and railings?" | P2 |
| 35, 38 | The finishing pass brings warm colour words ("honey-buff", "ochre") from a June pano lit by summer sun, three times today. Prefer overcast panos for colour; tighten the instruction. | P1 |
| 17 | Wrong window forms on the near building and the target's front come from the rough Cesium mesh; only words or an edit fix them. | P2 |

## G. Controls

| # | Finding | P |
| --- | --- | --- |
| 15 | Ticks for different steps sit together, with nothing saying which step each affects. | P2 |
| 40 | The date, time and weather panels look as if they apply to the keystone; they do not (noon, overcast, midwinter always). Grey them out with a note when the next step is a keystone. | P2 |
| 7 | The instruction dropdown defaulted to SI3.8, not SI3.9. Decide the default for a new user. | P3 |

## H. Results

| # | Finding |
| --- | --- |
| 37 | Measured: the finishing pass at 55 degrees across placed real details on the right building (blind panels on the corner block, the blue panelled door with rectangular transom, first-floor balconettes on the terrace) and caught a storey count to compare (it counted the basement, a known bug, and correctly did not apply it). At 105 degrees it added generic details tied to no building. |
| 39 | Decision: keystones are made from text only by default. The pano's work ends once it is words. |
| 42 | The bus problem in a fresh capture: parked-vehicle blobs in the lower right became an invented street junction. The capture step needs a way to say what is under the clutter. |
| 45 | A/B, same capture, text and seed. With the pano image (14:08): the return's door arched and black (wrong), the return's ground floor squared (right). Text only (14:14): the door blue in a plain case (right), the return's ground floor arched, a pediment invented. Both: the corner bay's second floor blind (should be glazed), the near building's first floor wrong. The pano image corrected nothing and probably caused the wrong door. Neither gets window counts right: that is the edit pass. |
| 29 | Withdrawn (lunch, not the tool). |

What worked: the LSA found the slope unprompted ("the junction with Nelson Street drops precipitously to the north") and the weft pass carried it in, replacing the pipeline's "level asphalt"; colour came out grey-tan; the near building's arched recesses with squared windows rendered correctly in both keystones; every keystone held the frame.

## Follow-up findings, 2026-10-20 (SI6 tests)

| # | Finding | P |
| --- | --- | --- |
| 47 | After a reload the subject line says "No subject set" until GO restores it, which reads as if the subject was lost. Say "Press GO to restore this view's subject", or restore the last view. | P2 |
| 48 | Choosing a preset in the dropdown does not load it; the hint "Still needed: standpoint, subject" does not mention the preset. Don's fix: the Load button lights up when a preset is selected and not loaded, and dims once loaded. The same lit/dim pattern for every choice that needs confirming (the pano's UPDATE). | P1 |
| 49 | Loading a preset silently unlinks the brief, and the unlinked brief silently blocks the stamp: every Excavate after a preset load went out unstamped, however often GO was pressed. Two silent steps make a failure the user cannot see or explain. | P1 |
| 50 | The brief's fields have no visible undo or history; one paste wiped a layout. The history line (A17) covers the brief too. | P2 |
| 51 | "Go to the view" needed asking about after two days with the tool. Step 1 of the step strip: "View: choose it and press GO", with the control beside it. | P1 |

## Follow-up findings, 2026-10-21 (A-1 tests and A-2)

| # | Finding | P |
| --- | --- | --- |
| 52 | In a layout, word count is weight. The distant Dublin Street end had a full sentence with a count; the corner building, the subject, had one clause; the Nelson Street return's blue door and steps were not mentioned and were not drawn. The layout field should prompt for the subject first and most fully (B6, B10). | P1 |
| 53 | Presets have no unsaved-changes mark, and loading one replaces what is in the brief without a word. Fixed in A-2: a line under Presets says "Changed since you loaded ...", Load fills the name box so Save shot overwrites, and loading over unsaved changes asks first. Tested. | P1 |
| 54 | The two run lists (Runs and keystones; the weft pass's LSA runs) look alike. Each needs a heading that says what it lists (B3). | P2 |
| 55 | A pass's status appeared inside the cropped pano preview, not near the button pressed. Fixed in A-2 with the progress card (A11). | P1 |
| 56 | "Scene layout" and "Scene text" are easy to confuse, in the editor title above all. Fixed in A-2: "Scene layout (your brief, left column: what the LSA reads)" and "Scene text (the selected run's: what the image model reads)". Tested. | P1 |
| 57 | Recorded as "the editor does not refresh after a pass". Corrected: the code refreshes the editor after every pass; most likely the editor was showing the Scene layout, not the Scene text (finding 56). The fix is the clearer title, not a refresh. | P1 |
| 58 | One stray touch in the frame moves the camera, and the Lock button scrolls out of sight while editing long fields further down: scroll down to edit, scroll back up, touch the frame, and the framing is lost and the setup repeats. Fixed in A-2: GO locks the camera in live mode. Tested; "a big one". | P1 |
| 59 | The GO status line (10 px, under the views list) is too small to notice: "I would have never seen it." Status that matters goes where the user is looking, at a readable size. Enlarged after the test; the frame's own lock badge and outline also show the state. | P1 |

Results, 2026-10-21. The progress card works: the pulsing dot and the seconds count show the run is alive, not frozen. The text-only LSA picture (late morning run, SI6.3) held Nelson Street's fall at about the right angle toward Northumberland Street, but drew the corner building with three floors above the street, dropping the attic storey, and left out the return's door and steps (finding 52). The layout said "four storeys above the street, the top floor flush with the facade": "flush" names a surface, not a count, and the model filed the attic under the roof (the same misreading as SI6.1's "three floors plus attic dormers").

| # | Finding (afternoon, weft pass) | P |
| --- | --- | --- |
| 60 | The weft report's removal check flags rewordings as losses: "four-storey" (the count came back reworded), "blind window" (now "blind panels"), "chimney stacks" (now "stone chimneys"). In the same report "steps" was a real loss: the near building's entrance steps were gone. False alarms teach the user to ignore the one that matters. | P1 |
| 61 | The weft pass overshot its own length cap: 2,840 characters against 2,600. | P3 |
| 62 | Proposals are not stable between passes. The same run and text gave "segmental arched" platts once and not the second time; "whinstone gutters" came back after it was removed. A REMOVE is forgotten by the next pass, and a proposal Don confirmed is lost unless he writes it into the layout. Decisions should stay with the view: removed stays out, kept becomes confirmed. | P1 |
| 63 | The weft pass swapped the tree species again (Ulmus glabra to Platanus x acerifolia), listed only under "verify". Evidence for A16. | P1 |
| 64 | The new fixtures and storey rules in the weft pass made no visible difference on the first test. The lamps were left out as "unconfirmed fixtures not verified in layout or visible composition" (the rule's "only where IMAGE 1 has room" gave the model its reason, and thin poles barely show in a capture); one roof sentence still covers every building; the layout's "flush with the facade" stayed, confirmed. The layout is confirmed and outweighs the instruction: what the director knows has to be in the layout. | P1 |

Results, afternoon. The LSA proposed a segmental arch under the platts, a detail Don had not noticed in eight months; he confirmed it in Street View (a subtle arcing sweep under the rigid steps; the solid ones probably enclose a cellar). The retaining wall along the descending return was kept: the basement areas read as moats around the buildings from the air. The progress overlay: "my new favorite thing", "I love that status gizmo".

## Follow-up findings, 2026-10-22

| # | Finding | P |
| --- | --- | --- |
| 65 | Too many presets to tell apart: 25 in all, nine for this one view, with nothing linking a preset to its view. The preset list should show only the presets saved for the view you are at (B2). | P2 |
| 66 | Unsaved brief changes are lost when the page closes or reloads, without a word: Don believed the new layout was saved and it was not. Fixed: the page asks before leaving with unsaved brief changes. | P1 |
| 67 | "Place", under "Where you stand", holds the subject's address (GO fills it from the subject marker), so every run is labelled "1 Nelson St" while the camera stands at 22 Abercromby Pl. Don: one field for the subject's location, one for the camera's, and every other field maps to one of them. Refinement: the pano keeps its own position, labelled as the photo's, since it is chosen to see the subject from wherever the best photo was taken (B4, B5). | P1 |
| 68 | The weft pass read the layout saved with the LSA run, not the layout in the brief: a corrected layout was silently ignored, twice. Fixed: the brief's layout is used when the brief is for the same place; the run preview warns when the run was made with an earlier layout. | P1 |
| 69 | Stray clicks while scrolling: an accidental REMOVE, the same class as the camera in 58. Rule: any one-click action that changes the text or the framing is reversible in one click where it happened (undo, don't ask). Fixed: PUT BACK after REMOVE. Tested. | P1 |
| 70 | After an Excavate the weft pass list kept the previous pick, so the pass ran on yesterday's run. Don: "another recurring confusion and causes more re-work." Fixed: the new run is selected and ADD LSA SURFACES lights up; the pass is never started automatically. | P1 |
| 71 | A "confirmed from your layout" item can carry the model's own words ("mutule", "fluted"). Fixed: a "Not in your layout" line lists them. Still too literal ("five-bay" for "five bays", "adjacent" for "next"). | P2 |
| 72 | The header "Weft pass from <LSA run id>" read as the time of the pass. Fixed: "Weft pass at 11:53, using the LSA run of 22 Oct, 10:01 and the scene layout in your brief now". | P2 |
| 73 | The layout was pasted into the Scene text through the floating editor: the editor shows whichever text was last clicked, the two look alike, and Close does not save (the editor writes as you type). Don: colour states (yellow while editing, green when done); the colour should also say which text is open (B1). | P1 |
| 74 | Auto-lock did not lock when GO was pressed with the still in the frame. Fixed: GO locks in either mode, and showing Cesium at the saved view locks too. | P1 |
| 75 | The weft pass was capped at 2,600 characters while the text was already 2,744, so it cut 600 characters and the length check rejected it (shown in red, text unchanged). Fixed: cap 2,900; when it must shorten it cuts the surface description of far elements first, never structure or the subject (level of detail by distance). | P2 |
| 76 | Polish, for the final visual pass: the status overlay's green reads as pea green. Don: traffic-light states (yellow running, red failed or not ready, green done or ready to press), with the words kept. | P3 |

Results, 2026-10-22.
- A text-only keystone (10:28) from a scene text written from the corrected layout: Nelson Street slopes down, the near building's arched recesses with square windows are right, the arch under the platts shows. Faults: arches carried round onto the return, and nearly every window blind, both from vague text ("blind window panels across two bays").
- With the full window pattern in the layout, the weft pass (11:53) confirmed the five bays, the rough-faced retaining wall, the blind and glazed pattern bay by bay and the flat-headed return, and removed nothing. Correction to the record: at 11:45 Claude called the weft pass unreliable at applying the layout; the layout in the brief was the old one, so the pass had never received the pattern.
- The LSA picture from the corrected layout (10:01) got Nelson Street's slope and the subject building right from text alone. The lamps are generic ("London fog"): a resident would spot them.

## Follow-up findings, 2026-10-22 afternoon (points of interest)

| # | Finding | P |
| --- | --- | --- |
| 77 | The edit panel took a paste meant for the Scene layout into the Scene text a second time; Close does not save. Fixed: a coloured band names the open text (amber BRIEF: SCENE LAYOUT, purple RUN: SCENE TEXT), a switch in the panel moves between the two, and Close became a green Done. Don: Done should go dark once clicked. | P1 |
| 78 | The way back to the points of interest is not obvious (they sit on the Cesium card, under the subject). Make it clearer in B1. | P2 |
| 79 | A sixth point got in through one path without the cap; the server refused to save it. Fixed. | P2 |
| 80 | Markers could not be moved; trying to move one added a point. Fixed: ↔ per point. Then: markers moved on any drag, and ↔ restarted the move instead of cancelling. Don: a dot must not move without the button, the button must show it is active, and the instruction must appear where the eye is. Fixed: only the point whose ↔ is lit can be dragged or moved; ↔ again or Esc cancels; an amber banner at the top of the frame says what to do. The panel's small buttons that scroll out of view remain (B1). | P1 |
| 81 | The frame scrolls out of sight while editing below it, so banners and the framing are missed. Fixed: the frame and its bar stay pinned at the top of the centre column. | P1 |
| 82 | The top strip wasted a band of height (the Weather note on its own line, the camera readouts wrapping). Fixed: one compact row; the keystone note sits beside the Weather title. | P2 |
| 83 | The model swapped the two faces of the corner block: the face turned toward the camera (the Nelson Street side) was taken for the front and given the front's arches; points on both faces had identical position words. Fixed: each point's position now says which way its surface faces ("on a face turned toward the camera", "on a face running away from the camera, facing right"), measured from the surface around the click. Result: square openings and door on the Nelson face, arches back on the front. | P1 |
| 84 | Text alone does not hold an irregular window pattern: bay by bay and floor by floor both came back as whole columns glazed or blind (one run, 15:07, got it right by chance); balustrades under alternate windows came back under every window. Goes to the edit pass. | P1 |
| 85 | "Narrow side panels" was drawn as glazed side windows; "blue" on two doors mixed them up. Describe what is there, positively, and tie each detail to its building ("on the near building on the left"). | P2 |
| 86 | A rectangular sash inside a round arched recess was drawn as an arched window (common in this part of town). Tried: the stone of the wall fills the half-round above a flat-headed window. Result pending. | P2 |
| 87 | Points of interest with "wrought-iron" and first-floor windows in one description produced iron balconies at the first floor. One element per point. | P2 |
| 88 | The run list is confusing: Don could not tell which keystone was the latest. Mark the newest and filter to the view (B2). | P1 |
| 89 | On Claude's side: steps and texts spread across several replies are hard to find again. Each set of steps goes in one message, in order, with the texts in it. | P1 |

Results, afternoon. The keystones from points of interest (14:12 to 15:30, text only, no pano: confirmed in the run record): the 19 Abercromby door dark and close to right, flower boxes right; once faces were named by how they sit to the camera, the Nelson face's openings and door came out square and the front's arches came back. Asked whether the accuracy of the roofline (chimneys, dormer attics, the flush parapet pair) meant the pano was used: it was not; the Cesium capture (Google's 3D tiles of the real street) is always sent as the frame, so roof forms and bay rhythm come from it.
