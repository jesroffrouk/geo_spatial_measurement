from typing import Any

from shapely.geometry import shape

from app.services.crs import to_utm

POLYGON_TYPES = {"Polygon", "MultiPolygon"}
LINE_TYPES = {"LineString", "MultiLineString"}
POINT_TYPES = {"Point", "MultiPoint"}


def _empty(note: str | None = None) -> dict[str, Any]:
    return {"area_sq_m": None, "length_m": None, "measured_in": None, "note": note}


def measure_feature(feature: dict[str, Any], source_crs: str) -> dict[str, Any]:
    geometry_type = feature["geometry_type"]

    if geometry_type is None:
        return _empty("Feature has no geometry.")
    if geometry_type in POINT_TYPES:
        return _empty()
    if geometry_type not in POLYGON_TYPES | LINE_TYPES:
        return _empty(f"Unsupported geometry type '{geometry_type}'; not measured.")

    geometry = shape(feature["geometry"])
    utm_geometry, utm_crs = to_utm(geometry, source_crs)

    result = _empty()
    result["measured_in"] = utm_crs
    if geometry_type in POLYGON_TYPES:
        result["area_sq_m"] = round(utm_geometry.area, 2)
    else:
        result["length_m"] = round(utm_geometry.length, 2)
    return result


def measure_features(features: list[dict[str, Any]], source_crs: str) -> list[dict[str, Any]]:
    results = []
    for feature in features:
        try:
            results.append(measure_feature(feature, source_crs))
        except Exception as exc:
            results.append(_empty(f"Could not be measured: {exc}"))
    return results
