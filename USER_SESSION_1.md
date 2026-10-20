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
