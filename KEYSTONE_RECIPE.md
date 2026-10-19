# Keystone recipe

How to make a keystone that keeps your camera's framing and gets the place right. Written 2026-10-18 from the Abercromby and Nelson tests, revised 2026-10-19 after user session 1 (USER_SESSION_1.md). The first draft of the step strip for the UI rebuild.

## The rule behind it

Cesium sets the frame; LSA decides what the scene contains; Street View is evidence, read into words. A pano image sent with the render pulls the camera toward the pano's own position, and on 2026-10-19 it corrected nothing the words had not. Words carry the evidence with no viewpoint to copy, so the keystone is made from text only. The pano's work ends once it is words.

## Steps

1. **View.** In the right-hand column, choose the saved view and press GO. If the camera floats above the street, press GO again until it sits at street level. Then leave the camera alone: Excavate and Synthesize stamp their runs with the view only if the camera is exactly on it.
2. **Brief.** Fill in the LSA brief. In the Scene layout, name the main elements one by one (the near building, the target, the terrace, the garden) and write what you know of each: windows, doors, railings, the slope. Whatever you leave out will not be confirmed later.
3. **LSA run.** Excavate. Check the run says it is stamped with the view.
4. **Capture.** Synthesize. This gives the capture and the pipeline's first scene text.
5. **Weft pass.** In the Runs and keystones card, select the new Synthesize run. Pick the LSA run by hand, check its preview, press ADD LSA SURFACES. Read the report: decide each proposed item, put back anything real that was removed, check species swaps against what you know, and read every sentence a REMOVE touched (it can leave a sentence broken).
6. **Finishing pass.** In the Street View card, set the newest overcast pano that sees the subject, aimed at it, about 55 degrees across (UPDATE, set the angles, UPDATE again). Press FINISHING PASS. Read the report: removed, added, disagreements. "No disagreements" only means nothing in the text could be contradicted.
7. **Director's edits.** Edit the scene text by hand: give each building its own sentence, put details on the right one, and replace any weather word (rain, sun, wet) or warm colour word the passes brought in with what the surface looks like under flat overcast light. Check the line under the box says "Edited by hand".
8. **Keystone.** Untick "Use this pano in MAKE KEYSTONE". Check the selected run is the capture, not a candidate. Seed 42. MAKE KEYSTONE; the compiler line must not say TRIMMED. The date, time and weather panels do not matter: keystones are always noon, overcast, midwinter.
9. **Check.** The framing line must say held; then C in the full-screen viewer, especially the far end of the street and the ground (the check measures building edges, not the slope). Check the summary line says no Street View reference.
10. **Approve.** APPROVE AS KEYSTONE on the candidate. It becomes the keystone for this view only.

## Traps we have hit

- Selecting a run replaces the text in the box with that run's own text. Select first, paste second.
- After MAKE KEYSTONE the new candidate is selected; a second MAKE KEYSTONE then builds from the candidate. Reselect the capture first (and paste the text again).
- Saving a view does not make it current; only GO does. The first GO can leave the camera in the air.
- The weft report and the finishing report describe the text as it was when they ran; they do not update after a hand edit.
- K in the full-screen viewer shows the view's approved keystone, not the selected run.
- A new pano needs UPDATE twice: once to load it, once to take your angles.
- The pano card remembers one pano per view; it does not know which job it is doing.
- "Use this pano in MAKE KEYSTONE" is ticked when the page loads.
- Negatives do not work in scene text: "none arched" invites arches. Describe what is there.
- Weather words do not belong in scene text: "rain-washed" pulls toward wet. Describe the mark, not its cause.
- Summer-sun panos push the stone warm (honey-buff, ochre). Take colour from overcast panos.
- Some details resist words (window counts in a bay, the globe-and-cap lamp, pediments, arches on the return). They are for the edit pass, not more wording.
- Parked vehicles in the capture become invented features (the bus problem). Say in the text what is really there.

## Abercromby and Nelson

- LSA Alignment: Abercromby and Nelson (55.7 m from the subject; heading 60.9, pitch 8.5, FOV 60). Best hand-built candidate 2026-10-19 10:13 (not approved: corner bay, return door, flat Nelson Street).
- LSA session 1: Abercromby and Nelson (50 m; heading 59, pitch 1.6, FOV 60). Session 1 runs: LSA 11:09 (not stamped), capture 11:33, keystones 14:08 (with pano) and 14:14 (text only).
- Evidence panos: JYFr07JvOuS78jFWLRHPMA (June 2025, 44 m), oQ-PbrZigkImB4CxVEM1tw (June 2025, 54 m), zi3ryjlonoAA8Xl25mFo3g (March 2021, 55.6 m; bare trees, fewer cars).
- Far right in these views: the straight end of Abercromby Place at Dublin Street, six three-bay houses (not London Street). The street is level in view; it falls from Albany Street to Broughton Street, out of frame.
- Seed 42.
