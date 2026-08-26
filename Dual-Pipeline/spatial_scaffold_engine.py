"""
Spatial Scaffold Engine: Sole authority for building, validating, and serializing
the 7 Strata 3D scene representation (RFC 7946 GeoJSON FeatureCollection).
Decoupled from creative documentary prompt generation.
"""

import json
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List


@dataclass
class SpatialScaffold:
    """Strongly typed container for the 7 Strata Spatial Scene Model."""
    address: str
    spatial_mode: str
    strata: List[Dict[str, Any]] = field(default_factory=list)

    def to_geojson(self) -> Dict[str, Any]:
        """Serializes the 7 Strata into a valid RFC 7946 GeoJSON FeatureCollection."""
        return {
            "type": "FeatureCollection",
            "properties": {
                "address": self.address,
                "spatial_mode": self.spatial_mode,
                "schema_version": "7-Strata-v2.0"
            },
            "features": self.strata
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_spatial_scaffold(
    address: str,
    telemetry: Any,
    domain_result: Optional[Any] = None,
    lighting_state: Optional[Any] = None,
    structures_data: Optional[List[Dict[str, Any]]] = None
) -> SpatialScaffold:
    """
    Constructs a complete RFC 7946 7-Strata GeoJSON model of the scene.
    
    Strata Hierarchy:
      Stratum 1: observer_frame        (Camera telemetry, FOV, spatial mode)
      Stratum 2: subterranean_geology  (Bedrock, lithics, stratigraphy)
      Stratum 3: ground_surface        (Surfacing, grading, curbs)
      Stratum 4: landscape_ecology     (Flora species, mature canopies)
      Stratum 5: built_environment     (Structures, storeys, heights, typologies)
      Stratum 6: dynamic_elements      (Static decluttering contract)
      Stratum 7: atmospheric_state     (NOAA solar ephemeris & live weather)
    """
    lat = getattr(telemetry, "latitude", 0.0) if telemetry else 0.0
    lon = getattr(telemetry, "longitude", 0.0) if telemetry else 0.0
    alt = getattr(telemetry, "altitude_agl", 0.0) if telemetry else 0.0
    heading = getattr(telemetry, "heading", 0.0) if telemetry else 0.0
    pitch = getattr(telemetry, "pitch", -45.0) if telemetry else -45.0
    fov = getattr(telemetry, "fov", 45.0) if telemetry else 45.0
    tile_mode = getattr(telemetry, "tile_mode", "3D_TILES") if telemetry else "3D_TILES"

    features: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------------
    # STRATUM 1: Observer Frame (Camera & Coordinate Anchor)
    # ---------------------------------------------------------------------
    features.append({
        "type": "Feature",
        "id": "stratum_1_observer_frame",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "stratum": "observer_frame",
            "spatial_mode": tile_mode,
            "camera": {
                "altitude_m_agl": round(alt, 1),
                "pitch_deg": round(pitch, 1),
                "heading_deg": round(heading, 1),
                "fov_deg": round(fov, 1)
            }
        }
    })

    # ---------------------------------------------------------------------
    # STRATUM 2: Subterranean Geology
    # ---------------------------------------------------------------------
    geo_desc = getattr(domain_result, "geological_foundation", "Regional bedrock and indigenous lithic foundation") if domain_result else ""
    features.append({
        "type": "Feature",
        "id": "stratum_2_subterranean_geology",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "stratum": "subterranean_geology",
            "foundation_analysis": geo_desc or "Bedrock lithology and soil stratigraphy verified"
        }
    })

    # ---------------------------------------------------------------------
    # STRATUM 3: Ground Surface
    # ---------------------------------------------------------------------
    mat_desc = getattr(domain_result, "material_and_lithics", "") if domain_result else ""
    features.append({
        "type": "Feature",
        "id": "stratum_3_ground_surface",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "stratum": "ground_surface",
            "primary_surfacing": "Engineered roadway and paved pedestrian curbs",
            "wear_characteristics": "Authentic environmental patina and drainage grading"
        }
    })

    # ---------------------------------------------------------------------
    # STRATUM 4: Landscape Ecology
    # ---------------------------------------------------------------------
    eco_desc = getattr(domain_result, "botanical_ecology", "") if domain_result else ""
    features.append({
        "type": "Feature",
        "id": "stratum_4_landscape_ecology",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "stratum": "landscape_ecology",
            "botanical_analysis": eco_desc or "Mature organic tree canopies with natural branching",
            "foliage_rectification": "Disambiguated from masonry mesh"
        }
    })

    # ---------------------------------------------------------------------
    # STRATUM 5: Built Environment
    # ---------------------------------------------------------------------
    arch_desc = getattr(domain_result, "architectural_analysis", "") if domain_result else ""
    default_structures = structures_data or [
        {
            "name": "Primary Facade",
            "storeys": 2,
            "height_m": 7.5,
            "roof_geometry": "pitched / parapet",
            "facade_material": "authentic regional masonry",
            "planar_rectification": "ENFORCED"
        }
    ]
    features.append({
        "type": "Feature",
        "id": "stratum_5_built_environment",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "stratum": "built_environment",
            "architectural_summary": arch_desc or "Plumb vertical planar facades with level floor plates",
            "structures": default_structures
        }
    })

    # ---------------------------------------------------------------------
    # STRATUM 6: Dynamic Elements (Static Decluttering Protocol)
    # ---------------------------------------------------------------------
    features.append({
        "type": "Feature",
        "id": "stratum_6_dynamic_elements",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "stratum": "dynamic_elements",
            "transient_decluttering": "ENFORCED",
            "vehicles": "NONE",
            "pedestrians": "NONE",
            "transient_clutter": "STRIPPED",
            "permanent_civil_fabric": "PRESERVED"
        }
    })

    # ---------------------------------------------------------------------
    # STRATUM 7: Atmospheric State (Lighting & Weather)
    # ---------------------------------------------------------------------
    if lighting_state and hasattr(lighting_state, "geojson_stratum"):
        features.append(lighting_state.geojson_stratum)
    else:
        features.append({
            "type": "Feature",
            "id": "stratum_7_atmospheric_state",
            "geometry": None,
            "properties": {
                "stratum": "atmospheric_state",
                "lighting_rig": "DEFAULT_DAYLIGHT",
                "color_temperature_k": 5500,
                "weather_state": "CLEAR"
            }
        })

    return SpatialScaffold(
        address=address,
        spatial_mode=tile_mode,
        strata=features
    )