```json
{
  "LSA_METADATA": {
    "PROJECT_NAME": "Ainslie Place Garden - North-West Aspect",
    "CENTROID_SUPPRESSED": "A glossy, romanticized Edinburgh postcard scene with uniform warm honey-toned stone, unnaturally clean asphalt, vivid monochrome yellow foliage, and generic manicured park lawns under light cosmetic rain.",
    "ACTIVE_DOMAIN_KEYS": [
      "Geology & Lithology (Craigleith Sandstone & Urban Pedology)",
      "Neoclassical Architectural Engineering (Gillespie Graham Ashlar & Ironwork)",
      "Dendrology & Canopy Ecology (Mature Temperate Deciduous Canopy)",
      "Atmospheric & Chemical Weathering (Auld Reekie Soot Patinas & Fluvial Hydrology)",
      "Optical Physics of Wet Surfaces (Rain-Drenched Fresnel & Diffuse Hemispherical Scattering)"
    ]
  }
}
```

### STAGE 1: CENTROID IDENTIFICATION & REJECTION
The generic AI baseline produces a sterile, tourist-brochure vision of Edinburgh’s New Town: monolithic golden-yellow buildings, clean pitch-black railings, pristine smooth lawns, and generic trees with uniform autumn leaves. This is suppressed. The authentic reality of the Moray Estate in mid-October is governed by Carboniferous quartz-arenite sandstone deeply impregnated with historic bituminous coal soot, mature weeping and spreading European deciduous hardwoods shedding into wet turf, oxidized cast-iron fixtures, and a cold, maritime North Atlantic rain that drenches vertical stone surfaces unevenly based on architectural overhangs.

---

### STAGE 2: DOMAIN KEY SELECTION & ACTIVATION

*   **Geology & Lithology Lens:** The facades of Ainslie Place (designed c. 1822 by James Gillespie Graham) are primarily dressed in Craigleith sandstone, an exceptionally durable, pale grey-buff Carboniferous sandstone with high quartz content and calcareous matrix. When saturated by rain, its albedo drops by 30–40%, shifting from pale drab-tan to a heavy, cold slate-buff. The garden soil is a heavy, dark clay-loam topsoil compacted over centuries of urban cultivation, currently waterlogged and displaying thin puddling in root-hollows.
*   **Neoclassical Architectural Engineering Lens:** The northwest quadrant features a grand four-storey classical pavilion with rusticated ground-floor masonry, deep-channelled V-joints, and giant-order attached Ionic or Doric pilasters spanning the piano nobile and second floor, capped by a substantial entablature, dentil cornice, and blocking course. Perimeter boundary treatments consist of heavy droved-ashlar dwarf walls topped by spear-topped wrought and cast-iron spearhead railings, socketed directly into stone copings using molten lead plugs.
*   **Dendrology & Canopy Ecology Lens:** Ainslie Place Garden's interior is dominated by mature specimen trees: *Fagus sylvatica* (European Beech), *Acer pseudoplatanus* (Sycamore), and *Tilia x europaea* (Common Lime). Mid-October at 55.95° N marks advanced senescence: foliage is ~45% fallen. Sycamore leaves are mottled with dark tar-spots (*Rhytisma acerinum*); beech leaves are drenched russet-copper and olive-brown. The bark of sycamore features flaking, puzzle-like plates revealing orange-buff under-bark, while beech trunks are smooth, dark lead-grey with vertical water rills.
*   **Chemical & Weathering Lens:** Two centuries of domestic coal burning ("Auld Reekie") left stubborn gypsum-soot crusts in rain-sheltered recesses: under window cornices, string courses, and the deep soffits of main eaves. In contrast, projecting string courses and vertical pilaster shafts have had soot washed clear by acidic precipitation, creating stark soot-streaked bi-tonal stone surfaces. At the perimeter fence, galvanic corrosion between the iron railings and lead-caulked copings has caused ferrous oxide leaching, staining the stone base in dull burnt-orange tongues.
*   **Optical Physics & Microclimate Lens:** 15:30 on October 15 in Edinburgh means the sun is low (~14° elevation), heavily diffused through unbroken, low-hanging stratocumulus clouds. Diffuse skylight (~6200K) produces soft, omnidirectional ambient occlusion with negligible direct shadows. Saturated surfaces (wet bark, wet leaves, flags, and saturated ashlar) exhibit heightened Fresnel reflectivity and anisotropic specular glints where micro-thin sheets of rainwater catch ambient daylight.

---

### STAGE 3: CROSS-DOMAIN SYNERGY ANALYSIS
*   **Sandstone Porosity × Atmospheric History × Rain Dynamics:** The Craigleith sandstone’s uneven soot mantle behaves differently when wet. Exposed rusticated ashlar stones become glossy and dark slate-tan, while the rain-sheltered gypsum/soot rinds under the heavy classical cornices remain matte, deeply charcoal-black, producing a sharp chiaroscuro inherent to the building’s material condition rather than direct sunlight.
*   **Canopy Architecture × Ironwork Boundary:** Water dripping from the overhanging beech and sycamore branches creates localized drip-lines along the perimeter ironwork and dwarf wall, accelerating moss (*Bryum argenteum*) and green microalgal biofilms (*Pleurococcus*) on the north-east and south-east faces of the stone copings.
*   **Leaf Litter × Soil Mechanics:** Saturated, decaying leaves form a compressed, multi-layered mat over the garden grass. The turf is coarse perennial ryegrass and meadow-grass (*Poa trivialis*), punctuated by worm casts and muddy root depressions where rainwater collects into glassy, dark puddles reflecting the white-grey sky.

---

### STAGE 4: DOMAIN CONFLICT RESOLUTION
*   *Conflict:* High-summer dense foliage would completely obscure the monumental neoclassical pavilion behind a green wall; dead winter bare branches would reveal the entire crescent but lose the autumn leaf focus requested.
*   *Resolution:* October 15 provides the exact phenological tipping point: sycamore and lime trees have thinned extensively, with lower interior branches mostly bare and upper outer canopies holding ragged clusters of yellow-brown and ochre foliage. This permits the monumental pilasters, sash windows, and soot-streaked pediments of the central pavilion to register legibly through the dripping, sculptural lattice of wet trunks and branches.

---

### STAGE 5: PARAMETER-READY MAPPING
*   **Diffuse Albedos:** Sandstone (dry: `0.45, 0.42, 0.38`; wet: `0.22, 0.20, 0.18`), Soot crusts (`0.04, 0.04, 0.05`), Wet Sycamore bark (`0.12, 0.10, 0.08`), Decomposing Leaf Litter (`0.28, 0.15, 0.04` to `0.18, 0.12, 0.05`).
*   **Roughness Maps:** Saturated ashlar `0.35–0.45` with specular puddling pockets `0.05`; wet tree trunks `0.25–0.40` along water tracks; iron railings `0.30` with coarse rust blooms `0.85`.
*   **Lighting Environment:** Low-altitude diffuse dome light, CCT 6200K, low overcast, uniform downward illuminance, zero hard shadow casting, high ambient wet-sheen fresnel response.

---

---RENDER_PROMPT---
Generate a photorealistic documentary photograph of the historic private garden in Ainslie Place, Edinburgh, looking toward the grand Georgian sandstone crescent. The camera is positioned at eye level in the center of the communal oval garden, facing north-west, framing a medium view through wet mature trees and across the perimeter iron railings toward the monumental four-storey central neoclassical pavilion and its adjoining terraced townhouses. 

In the immediate foreground, the south-east-facing bark of a mature sycamore tree and a European beech trunk are drenched with steady rain, displaying deep slate-brown and charcoal tones with slick vertical rills of water, patches of pale crustose lichen, and green microalgae caught in the bark fissures. The ground is covered in lush, sodden grass strewn with a dense carpet of wet, fallen autumn leaves in shades of copper-brown, dull ochre, and spotted olive, with small reflective rainwater puddles nestled between exposed tree root flares. 

Through the thinning, wet autumn canopy, the dark wrought-and-cast-iron perimeter fence stands along a low sandstone dwarf wall, its black painted bars weathered with chips and faint streaks of orange rust at the lead-caulked bases. Beyond the railings, across the dark, wet asphalt roadway, the north-west crescent's central pavilion dominates the background with its Craigleith sandstone ashlar facade darkened by rain, showcasing classical rusticated masonry on the ground level, colossal pilasters above, tall multi-pane timber sash windows, and dark soot-stained patinas preserved under the heavy projecting cornices and window pediments. 

The light is the soft, flat, cold diffuse daylight of an overcast Scottish autumn mid-afternoon, rendering high surface wetness, glossy reflections on the stone sills, railings, and waterlogged paths, and an atmospheric sky shrouded in pale grey, unbroken rain clouds.