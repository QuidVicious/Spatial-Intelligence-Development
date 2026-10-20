# Rebuild spec: fixes and flow, then the final pass

Written 2026-10-20 from USER_SESSION_1.md (finding numbers in brackets) and DECISIONS.md. Approach agreed with Don: fix what is wrong and how the tool flows now, improving as we go; the final visual UI comes last, once the Google and Mapillary sources are both in, so nothing is designed twice.

Three kinds of work, in this order:
- **Round A: fixes.** Bugs, prompt rules, and small changes that stop the tool misleading a user. No new layout.
- **Round B: flow.** The step strip, gating, one name per thing, the evidence card. Structure, not styling.
- **Round C: after Mapillary.** The new source, the location model, then the final visual pass and user session 2.

## Round A: fixes

### Prompts (Dual-Pipeline, domain_engine.py)
| # | Fix | From |
| --- | --- | --- |
| A1 | Weathering rule in the weft pass and finishing pass instructions: describe weathering by its visible marks (pale, cleaner, streaked, crusted, bleached), never by the weather that made it (rain, sun, wind, wet). Location-neutral wording; examples from several kinds of place, not only masonry. The flagged-word check explains itself: "weather word: describe the mark instead". | [27] |
| A2 | Colour rule in the finishing pass: name colours as they would look under flat overcast light; warmth from sunlight is light, not stone. Report the pano's season in the report so a summer pano is visible. | [35] [38] |
| A3 | The finishing pass counts floors of windows above the ground the viewer stands on; floors below street level are not counted (same rule as the weft pass). | 2026-10-18 |

### Flow bugs (LSA-Studio, pipeline.js and lsa_studio.html)
| # | Fix | From |
| --- | --- | --- |
| A4 | The stamp depends on where the camera is, not on whether the brief is linked (root cause: loading a preset unlinks the brief, and an unlinked brief stamps nothing [49]). SAVE makes the saved view the current view, as GO does. Excavate and Synthesize show "Will be stamped with: [view]" or "Not stamped: camera has moved from [view]" before they run. | [6] [8] [11] |
| A5 | The first GO after "Show Cesium in the frame" leaves the camera in the air. Find the cause (likely the jump runs before the frame resizes or the tiles load) and make one GO land on the street; until then show "Loading the view". | [14] |
| A6 | After MAKE KEYSTONE the source capture stays selected (the new candidate is shown, not selected), or MAKE KEYSTONE on a candidate uses that candidate's capture. Never a candidate of a candidate. | [44] |
| A7 | "Use this pano in MAKE KEYSTONE" starts unticked (text only is the default). The confirm dialog says "Text only" or "With pano image: [id]". | [39] [41] |
| A8 | The LSA dropdown refreshes when an Excavate finishes and when the page regains focus. | [10] |
| A9 | Empty states name the next step: "No capture of this view yet: press Synthesize"; "No LSA run for this view yet: press Excavate". Replace "replayable". | [12] |
| A10 | The viewfinder labels what it shows: "LSA image", "Capture", "Keystone candidate", "Keystone". | [13] |
| A11 | Excavate, the weft pass and the finishing pass use the same stepper and centred status as Synthesize: started, running, done, failed. | [5] [16] |
| A12 | The date, time and weather panels show "Keystones always use noon, overcast, midwinter" and grey out when the next step is a keystone. | [40] |
| A18 | The instruction dropdown defaults to SI6.2 (adopted 2026-10-20), not the first in the list; the server default matches. | [7] |
| A19 | Preset Load button lights up when a preset is selected and not yet loaded, dims once loaded; the "Still needed" hint mentions the preset. Same lit/dim pattern for the pano's UPDATE. | [48] |
| A20 | After a reload, the subject line says "Press GO to restore this view's subject" instead of "No subject set". | [47] |

### Reports (both passes)
| # | Fix | From |
| --- | --- | --- |
| A13 | REMOVE cuts cleanly: it removes the clause, repairs the join, and shows the sentence before and after. If it cannot repair the join it says so beside the item, not in a line above. | [26] |
| A14 | A report is marked stale when the text changes after it ("From the weft pass at 11:41; text edited since"). | [30] |
| A15 | Each item shows its sentence, a plain gloss for specialist words, and what happens if you do nothing. | [20] [23] |
| A16 | Species changes are listed as changes to approve ("Ulmus glabra replaced by Fagus sylvatica: KEEP the old / TAKE the new"), not only under "verify". | [28] |
| A17 | A history line under the scene text: each pass, hand edit and paste, with time and source; UNDO steps back through it. | [33] |

## Round B: flow

| # | Change | From |
| --- | --- | --- |
| B1 | Step strip across the top: View, Brief, LSA run, Capture, Add LSA synthesis, Street View check, Edit, Keystone, Approve. It shows where you are, what is next, and what you have made at each step (with links). Based on KEYSTONE_RECIPE.md. | [10] |
| B2 | Gating: only the current step's controls are active; later steps are shown but closed with a line saying what they need. Lists filter to the current view. | [9] [22] [15] |
| B3 | One name per thing, everywhere on screen (proposal below; Don decides). Internal names (weft, warp, keystone recipe) stay in code and docs. | [2] [19] |
| B4 | One place sets the location; the address field, the Cesium search and the saved view follow it. | [1] |
| B5 | The source-neutral evidence card: replaces the pano card. Each item has source, image, position, heading, date and season, role ("read for detail; never copied into the image"), licence and attribution. It proposes the best image for the job: for the Street View check, aimed at the subject, about 55 degrees across, newest overcast. | [4] [31] [32] [37] DECISIONS 2026-10-20 |
| B6 | The brief's layout field asks for the main elements one by one (near building, subject, beyond, ground, greenery) with prompts: "What do you know about its windows, doors, railings? Does the street slope?" | [24] [34] |
| B7 | Scene text written element by element: the pipeline's first text and every pass keep one labelled section per element, so details land on the right building. Method change in domain_engine.py; the compiler joins the sections for the image model. | [34] [43] [46] |
| B8 | Under-clutter note at capture: "What is really under the parked cars?" One line the user can fill, sent with the scene text. | [42] |
| B9 | Layout names are checked like everything else: street and place names in the layout are shown back with what the tool found there, and a mismatch is flagged rather than confirmed. | [25] |
| B10 | Points of interest: the subject plus up to four more markers placed on the Cesium frame, each with a short description the user writes and a rank (1 = most important) the user sets. The compiler opens the scene section with a priority block: the points in rank order, each as its own element entry with its position worked out from the marker (side, height in frame, distance) and the user's description, followed by the rest of the scene with no repeats. The task and framing rules stay ahead of the block. Ranks and labels show in the UI but never reach the image model as numbers or labels (it can draw them); order and wording carry the rank. Each point also aims an evidence crop, marks an edit region for the edit pass, and is a place the framing check measures (including the ground). Test before trusting: A/B with the ranking reversed, to measure whether order changes the render. Per point, the evidence step: pick the image that sees the point best (close, facing it, unobstructed, right season), crop to it, show the crop as a thumbnail for the user to confirm, read it into words for that element only (the user's description stays confirmed; the sketch's additions come in as proposed), and never send the image to the renderer. | Don 2026-10-20; [43] [46] |

### Names (agreed with Don 2026-10-20; the Synthesize button becomes CAPTURE so "synthesis" names one step only)
| On screen | Was | Means |
| --- | --- | --- |
| View | saved view | Where the camera stands and looks |
| Brief | preset, shot | What you tell the LSA about the place |
| LSA run | excavation | The LSA's analysis (and its own picture) |
| Capture | Synthesize (button and run) | The Cesium frame and the pipeline's first text; the button reads CAPTURE |
| Add LSA synthesis | weft pass, ADD LSA SURFACES | Bring the LSA's findings into the scene text |
| Street View check | finishing pass | Read a street photo into the scene text |
| Scene text | scene text, woven text | The description the image model reads |
| Keystone | keystone | The approved master image for a view |

## Round C: after Mapillary
- C1 Mapillary as an evidence source in the evidence card (client token in the .env file, images near the camera ranked by distance, facing and season, 2048 px).
- C2 Street furniture from Mapillary map features into the brief and the place primer.
- C3 The location model: element records (JSON) built from many vantage points; scene text assembled from the elements in frame.
- C4 Final visual pass on the whole UI. Don's direction: camera metaphors throughout; the viewport as the ground-glass plate of a view camera (the right way up), with a toggleable grid overlay.
- C5 User session 2 with outside testers; compare with session 1.

## Parked, with reasons
- Edit pass (window counts, the lamp, doors): after Round B, so it lands in the step strip.
- Place primer: with C2 and C3.
- Sketch set from CC photos (Geograph, Wikimedia Commons, Mapillary), aerial and historical views: after C3.
- Privacy statement: written alongside the job applications; it does not wait for code.
