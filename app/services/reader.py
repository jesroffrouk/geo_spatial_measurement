from dataclasses import field,dataclass
from pathlib import Path
import geopandas as gpd
import zipfile
from typing import Any
import pandas as pd
import json
from shapely.geometry.base import BaseGeometry

KML_DEFAULT_CRS="EPSG:4326"

class FileReadError(Exception):
    """Base Class: Upload couldn't be read"""


class UnsupportedFileTypeError(FileReadError):
    pass

class InvalidFileError(FileReadError):
    pass

@dataclass
class ReadResult:
    features: list[dict]
    crs: str | None
    warnings: list[str] = field(default_factory=list)

def read_geo_files(path:Path) -> ReadResult:
    # checking if it's kml file
    # checking if it's shaped files
    suffix = path.suffix.lower()
    if suffix == ".kml":
        gdf,warnings = _read_kml(path)
    elif suffix == ".zip":
        gdf,warnings = _read_zipped_files(path)
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Upload a .kml or a .zip containing a Shapefile."
        )
    if len(gdf) == 0:
        raise InvalidFileError("This file contain no features")

    crs = gdf.crs.to_string() if gdf.crs else None

    if crs is None:
        warnings.append("No crs found in file , can't be trusted until it is known")
    return ReadResult(features=_extract_features(gdf,crs),crs=crs,warnings=warnings)

def _read_kml(path: Path) -> tuple[gpd.GeoDataFrame,list[str]]:
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        raise InvalidFileError(f"couldn't parse KML file: {exc}") from exc

    if gdf.crs == None:
        gdf = gdf.set_crs(KML_DEFAULT_CRS)

    # clean up empty ones later on
    # gdf = gdf.dropna(axis=1,how='all')
    return gdf,[]

def _read_zipped_files(path: Path) -> tuple[gpd.GeoDataFrame,list[str]]:
    if not zipfile.is_zipfile(path):
        raise InvalidFileError("The uploaded file is not valid zip archive")

    with zipfile.ZipFile(path) as zf:
        shp_names = sorted(n for n in zf.namelist() if n.lower().endswith(".shp"))

    if not shp_names:
        raise InvalidFileError("The zip archieve doesn't contain .shp file")

    warnings = []
    if len(shp_names) > 1:
        warnings.append(f"Zip contains {len(shp_names)}; only {shp_names[0]} was read")

    try:
        gdf = gpd.read_file(f"zip://{path}!{shp_names[0]}")
    except Exception as exc:
        raise InvalidFileError(f"couldn't read shapefile: {exc}") from exc

    return gdf,warnings


def _extract_features(gdf: gpd.GeoDataFrame, crs: str | None) -> list[dict[str, Any]]:
    """Convert a GeoDataFrame into a list of plain, JSON-friendly dicts."""
    geom_col = str(gdf.geometry.name)
 
    attributes_df = pd.DataFrame(gdf.drop(columns=[geom_col]))
    attributes: list[dict[str, Any]] = json.loads(
        attributes_df.to_json(orient="records", date_format="iso") or "[]"
    )
 
    geometries: list[BaseGeometry | None] = list(gdf.geometry)
 
    features: list[dict[str, Any]] = []
    for index, (geom, props) in enumerate(zip(geometries, attributes)):
        if geom is None or geom.is_empty:
            geometry_type = None
            geometry = None
        else:
            geometry_type = geom.geom_type
            geometry = dict(geom.__geo_interface__)
 
        features.append(
            {
                "index": index,
                "geometry_type": geometry_type,
                "geometry": geometry,
                "crs": crs,
                "properties": props,
            }
        )
    return features
