from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform


class CRSError(Exception):
    pass

def utm_epsg_for(lon: float,lat: float) -> int:
    zone = int((lon + 180) / 6) + 1
    if lon == 180.0:
        zone = 60

    return 32600 + zone if lat >= 0 else 32700 + zone

def looks_like_lonlat(bounds: tuple[float,float,float,float]) -> bool:
    return -180 <= bounds[0] and bounds[2] <= 180 and -90 <= bounds[1] and bounds[3] <= 90


def resolve_source_crs(crs: str | None, bounds: tuple[float,float,float,float]) -> tuple[str,str | None]:
    if crs is not None:
        return (crs,None)
    else:
        if looks_like_lonlat(bounds):
            return ("EPSG:4326","crs is none we can assume it but not confirmed yet")
        else:
            raise CRSError("crs is none bound doesn't look like lat/lon")


def to_utm(geometry: BaseGeometry, source_crs: str) -> tuple[BaseGeometry, str]:

    to_degrees = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    centroid = geometry.centroid
    lon, lat = to_degrees.transform(centroid.x, centroid.y)

    utm_crs = f"EPSG:{utm_epsg_for(lon, lat)}"

    to_meters = Transformer.from_crs(source_crs, utm_crs, always_xy=True)
    return transform(to_meters.transform, geometry), utm_crs
