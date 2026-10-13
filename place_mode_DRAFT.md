## MODE: REALIZE THE PLACE (addendum to SI3.x)

DRAFT for review, 2026-10-12. Not yet used by the tool.

This run realizes a whole place, not a shot. There is no camera, no framing and no moment. Work out what this address IS: every structure, surface, plant and hidden element, and how each came to look the way it does. Later passes choose what a given shot sees; this pass forgets nothing.

### What to include
- Every element of the place: each building or house in a terrace, each run of railing, each tree or group of trees, the ground surfaces, street furniture, drainage, retaining structures.
- Hidden elements (vaults, drains, foundations, culverts) are included and marked hidden. They inform the visible ones.
- Per element: its form (for a building, storeys, bays, openings, roofline), its materials and how they were worked, its condition as it looks today (surface first, actual colours, where soiling and growth concentrate), and its biology (moss, lichen, algae, and where each grows).
- Species by Latin and common name, with bark character, because bark governs where moss, lichen and moisture settle.
- The character of the place in prose: microclimate, drainage, soot and cleaning history, how it was planned and built, and how ground and buildings have pushed against each other since.

### What to leave out
- The moment: season, leaf state, fallen leaves, weather, wetness, light, time of day, sky. Name anything you set aside in moment_excluded, in one line.
- Anything transient: vehicles, people, bins, signs, scaffolding, planting in window boxes or tubs.
- Anything that can be lifted off is not permanent. Its fixing is: a window box bracket or ledge, a balconette, a boot scraper, a lamp standard, a railing, a fanlight.

### How sure you are
- Everything in this pass is recalled, not seen. Mark each element's confidence: high, medium or low.
- Structure (forms, ornament, openings) is the least reliable thing to recall. Describe it plainly and mark it medium or low unless it is famous and well documented. Evidence will confirm or correct it.
- State when each recalled fact is true. Condition and biology change with air quality, cleaning and planting over decades. Say which period your knowledge describes ("present day", "before stone cleaning", "as built"), and prefer the present day. If you only know an earlier state, say so rather than presenting it as current.

### Output
Return ONE JSON object and nothing else: no Markdown fence, no text before or after. It must be valid JSON: double quotes only, no comments, no trailing commas, no line breaks inside strings (write them as \n).

{
  "lsa_metadata": {
    "place_name": "string",
    "centroid_suppressed": "string",
    "active_domain_keys": ["string"]
  },
  "place": {
    "name": "string",
    "address": "string",
    "built": "string: period and phases",
    "designers": ["string"],
    "character": "string: prose, the essential truth of the place, no moment"
  },
  "elements": [
    {
      "id": "string: short slug, unique, stable (for example terminal-house-ne, railing-garden-north)",
      "name": "string",
      "kind": "building | ironwork | tree | planting | ground | wall | street-furniture | drainage | other",
      "where": "string: position in plain words, relative to other elements",
      "structure": "string",
      "materials": "string",
      "condition": "string: as it looks today, surface first, actual colours",
      "biology": "string",
      "hidden": false,
      "permanence": "permanent | seasonal",
      "confidence": "high | medium | low",
      "true_as_of": "string",
      "source": "recalled"
    }
  ],
  "species": [
    {
      "latin": "string",
      "common": "string",
      "where": "string: element ids or plain words",
      "bark": "string",
      "confidence": "high | medium | low",
      "true_as_of": "string",
      "source": "recalled"
    }
  ],
  "moment_excluded": "string"
}
