# Keystone recipe

How to make a keystone that keeps your camera's framing and gets the place right. Written 2026-10-18 from the Abercromby and Nelson tests; the first draft of the step strip for the UI rebuild.

## The rule behind it

Cesium sets the frame; Street View is evidence. A pano image sent with the render pulls the camera toward the pano's own position (the camera position is in every photo of the subject, even a tight crop). It is safe only when the pano was taken from where your camera stands. Words carry the pano's evidence with no viewpoint to copy.

## The two panos, and their jobs

| Job | Pano | Why |
| --- | --- | --- |
| Evidence pano: words only, via the FINISHING PASS | the newest pano (current colours and surfaces) | It never reaches the image model as a picture, so its position does not matter |
| Reference image: sent with MAKE KEYSTONE | the pano taken closest to your camera, ideally in a bare-tree season with few cars | Its position must agree with your camera: check "m from subject" against your view's distance |

## Steps

1. **View and source run.** Choose the saved view in the Runs and keystones card, then select its Synthesize run (the capture). Do this FIRST: selecting a run reloads its own scene text over anything pasted.
2. **Scene text.** Click "Edit this run's scene text below", then paste the working text. Check the line under the box says "Edited by hand".
3. **Evidence pano.** In the Street View card, set the newest pano (paste its ID, press UPDATE, set heading, pitch and FOV, press UPDATE again).
4. **Finishing pass.** Press FINISHING PASS. Read the report under the status line:
   - Removed: should say none. If not, put back what is real.
   - Added from the pano: check each.
   - Where the pano seems to disagree: decide each one; edit the text by hand if the pano is right (and correct the Scene layout).
5. **Reference pano.** Set the matched pano (paste its ID, UPDATE, angles, UPDATE again). Check "m from subject" is within a metre or two of your view's distance. Tick "Use this pano in MAKE KEYSTONE"; set "What MAKE KEYSTONE sends" to Full view.
6. **Seed.** Type the seed (42 for comparisons).
7. **Make keystone.** Watch the Prompt Compiler line: the budget may be raised to fit; it must not say TRIMMED.
8. **Check.** The framing line under the run list must say held. Then compare with the capture by eye: C in the full-screen viewer, especially the far end of the street.
9. **Approve.** APPROVE AS KEYSTONE on the new candidate. It becomes the keystone for this view only.

## Traps we have hit

- Selecting a run replaces pasted scene text with the run's own text. Select first, paste second.
- K in the full-screen viewer shows the view's approved keystone, not the selected run.
- A new pano needs UPDATE twice: once to load it, once to take your angles.
- The pano card remembers one pano per view; it does not know which job it is doing.
- "Framing vs capture: held" is measured on the strongest edges (usually the main building). Check the far end by eye.
- Negatives do not work in scene text: "none arched" invites arches. Describe what is there.
- Some details resist words (arched return windows, the corner door, pediments, the globe-and-cap lamp). They are for the edit pass, not more wording.
- Older panos show older colours: take surfaces from the newest pano.
- "What MAKE KEYSTONE sends" defaults to Detail crop, and step 5 is easy to miss. The 16:08 keystone on 2026-10-18 went out with the Detail crop by mistake and still held the frame (4 px), so at a matched pano either setting holds. Keep one setting across a comparison and note which one the run used.
- Colour words travel. "Honey-buff" from the pano passes pushed the stone yellow; Don reads it as tan-grey that changes with the light. Name the colour as it looks under flat overcast light.

## Abercromby and Nelson, current set (2026-10-18)

- View: LSA Alignment: Abercromby and Nelson (55.7 m from the subject; heading 60.9, pitch 8.5, FOV 60).
- Source run: Saturday 2026-10-17 12:00 Synthesize.
- Evidence pano: oQ-PbrZigkImB4CxVEM1tw (June 2025, 54 m from the subject).
- Reference pano: zi3ryjlonoAA8Xl25mFo3g (March 2021, 55.6 m; bare trees, fewer cars, London Street visible), heading 60, pitch 10, FOV 60.
- Seed 42.
- Candidate 2026-10-18 16:08: held the frame (no measurable change). Don: overall good; one blind window too many (the corner bay, second floor, should be glazed); stone too yellow. Also: the near building has no basement railings. Re-render with the colour, window-pattern and railings wording (text in HANDOFF_2026-10-19.md), same settings.
