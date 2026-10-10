# Geospatial File Measurement API

A REST API built with **FastAPI** that accepts a geospatial file (**KML** or a **zipped Shapefile**), extracts every feature in it, and returns accurate **area** (polygons) and **length** (lines) measurements in square meters and meters.

The key idea: coordinates stored in degrees (latitude/longitude) cannot be measured directly. Each geometry is first reprojected into a meter-based **UTM** coordinate system, and only then measured.

---

## Table of contents

1. [Features](#features)
2. [Setup](#setup)
3. [API documentation](#api-documentation)
4. [Architecture](#architecture)
5. [Design decisions](#design-decisions)
6. [Limitations](#limitations)
7. [What I learned](#what-i-learned)
8. [Future scope](#future-scope)

---

## Features

- Upload a `.kml` file, or a `.zip` containing a Shapefile.
- Extracts, for every feature: its index, geometry type, geometry, CRS and attributes.
- Handles any source CRS (degrees, meters, feet, any UTM zone, Web Mercator...).
- Chooses a UTM zone for each feature and reprojects before measuring.
- Area for `Polygon` / `MultiPolygon`, length for `LineString` / `MultiLineString`.
- Points are returned without a measurement, and unsupported geometry types are skipped with an explanatory note instead of crashing.
- Handles a missing CRS (for example a Shapefile without a `.prj`) explicitly.
- Clear error responses for invalid, corrupt or unsupported uploads.
- Results are stored in SQLite so they can be retrieved later by file id.

---

## Setup

**Requirements:** Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install dependencies into a local virtual environment
uv sync

# 3. Start the server
uv run uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** for the interactive API documentation, where every endpoint can be tried from the browser.

Run `uvicorn` from the project root. The database file `geo.db` and the `uploads/` folder are created there automatically.

### Sample data (that I have used)

| File | Contents | Purpose |
|---|---|---|
| `mixed.kml` | Polygon, LineString, Point and MultiPolygon | Every geometry type in one file |
| `polygons.zip` | Zipped Shapefile with Polygon + MultiPolygon | Normal Shapefile case |
| `lines.zip` | Zipped Shapefile with a LineString | Length measurement |
| `polygons_no_prj.zip` | Same polygons, `.prj` removed | Missing CRS |
| `corrupt.zip` | Not a real zip | Invalid upload |

The script also prints the **expected values** calculated directly on the WGS84 ellipsoid, which serve as an answer key for the measurements.

---

## API documentation

### `POST /api/files/`

Upload and process a file. Send it as `multipart/form-data` with the field name `file`.

**Response `201 Created`**

```json
{
  "file_id": "66c9be46bbb649f6ae32dcc3afb14b99",
  "filename": "mixed.kml",
  "status": "completed",
  "crs": "EPSG:4326",
  "feature_count": 4,
  "warnings": [],
  "created_at": "2026-10-10T06:50:59.276657"
}
```

**Errors**

| Status | When |
|---|---|
| `400` | Unsupported extension, corrupt zip, zip without a `.shp`, unreadable KML, or a missing CRS that cannot be safely assumed |
| `422` | No file was sent |

### `GET /api/files/{file_id}/`

File-level information: filename, status, CRS used, feature count and any warnings. Returns `404` for an unknown id.

### `GET /api/files/{file_id}/measurements/`

Per-feature details and measurements. Returns `404` for an unknown id.

**Response `200 OK`**

```json
{
  "file_id": "66c9be46bbb649f6ae32dcc3afb14b99",
  "crs": "EPSG:4326",
  "feature_count": 4,
  "features": [
    {
      "index": 0,
      "geometry_type": "Polygon",
      "geometry": { "type": "Polygon", "coordinates": [[[85.0, 20.0, 0.0], "..."]] },
      "crs": "EPSG:4326",
      "properties": { "Name": "Square plot", "category": "plot" },
      "area_sq_m": 995102.03,
      "length_m": null,
      "measured_in": "EPSG:32645",
      "note": null
    },
    {
      "index": 1,
      "geometry_type": "LineString",
      "area_sq_m": null,
      "length_m": 3200.15,
      "measured_in": "EPSG:32645",
      "note": null
    },
    {
      "index": 2,
      "geometry_type": "Point",
      "area_sq_m": null,
      "length_m": null,
      "measured_in": null,
      "note": null
    }
  ]
}
```

Every feature always has the same keys. A measurement that does not apply is `null`. `measured_in` says which UTM zone was used, and `note` explains anything that was skipped or failed.

---

### Why reproject at all?

Latitude and longitude are angles on a curved surface, not distances on a flat one. One degree of latitude is about 111 km everywhere, but one degree of longitude shrinks toward the poles. Measuring the area of a polygon in degrees gives a number in meaningless "square degrees". Reprojecting into a meter-based CRS makes ordinary flat geometry valid.

### The two input formats

- **KML** is a single XML file and is always in EPSG:4326 by specification.
- **A Shapefile** is a set of files (`.shp` geometry, `.dbf` attributes, `.shx` index, `.prj` CRS) that must stay together, which is why it is uploaded as a `.zip`. Its CRS can be anything, and the `.prj` may be missing.

### The UTM strategy

UTM divides the world into 60 zones, each 6 degrees of longitude wide, and each zone's projection is very accurate within itself.

1. Take the centroid of the feature and convert it to lon/lat degrees.
2. Zone number: `int((lon + 180) / 6) + 1`, capped at 60.
3. EPSG code: `32600 + zone` in the northern hemisphere, `32700 + zone` in the southern.
4. Convert the feature's coordinates from the source CRS to that UTM CRS and measure.

This works whatever the source CRS is, because pyproj converts from any CRS to any other.

### Missing CRS

If a Shapefile has no `.prj`, the API does not silently guess:

- If the coordinates fit within valid lon/lat ranges (x in -180..180, y in -90..90), it assumes **EPSG:4326** and adds a warning to the response.
- Otherwise the upload is rejected with `400`, since the coordinates could be in meters or some unknown system.

---

## Architecture

```
geo-measure-api/

├── app/
    ├── db/
    │   ├── models.py        # SQLAlchemy tables: File, Feature
    │   ├── database.py      # SQLite engine, session, get_db dependency
    │   ├── schemas.py       # Pydantic response models
    │
    ├── services/
    │       ├── reader.py    # KML / zipped Shapefile -> feature dicts
    │       ├── crs.py       # UTM zone selection, CRS resolution, reprojection
    │       └── measure.py   # area / length calculation per feature
    ├── main.py              # main file with fast api routes
├── sample_data/         # generated test files
├── pyproject.toml
└── README.md
```

| Module | Responsibility | Knows about |
|---|---|---|
| `reader.py` | Read files and extract features | geopandas only |
| `crs.py` | Decide which CRS to use and reproject | pyproj, shapely |
| `measure.py` | Turn features into measurements | `crs.py`, shapely |
| `models.py` / `database.py` | Persistence | SQLAlchemy |
| `schemas.py` | Shape of API responses | Pydantic |
| `main.py` | HTTP layer that glues everything together | all of the above |

The reader, CRS and measurement modules are plain Python with no knowledge of FastAPI or the database, so each can be run and checked on its own.

## Design decisions

- **UTM chosen per feature, from its centroid.** One zone for a whole file would be less accurate if the file covers a large region. The cost of choosing per feature is negligible.
- **Reproject a temporary copy.** The geometry stored and returned stays in the file's own CRS. The UTM copy exists only to do the math.
- **Always reproject, even if the source is already in meters.** "In meters" does not mean "good for measuring". Web Mercator is in meters but inflates areas heavily away from the equator, and some CRSs use feet.
- **Report a missing CRS, then decide separately.** The reader only reports `crs=None`. `crs.py` makes the decision. Each module does one job.
- **Zip files are read in place** with GDAL's `zip://` path instead of being extracted, which avoids "zip slip" attacks (archives that try to write outside their folder).
- **Uploads are saved under a generated UUID name**, never under the user-supplied filename.
- **Custom exceptions** (`FileReadError`, `InvalidFileError`, `UnsupportedFileTypeError`, `CRSError`) are caught in the route and turned into clean `400` responses.
- **One bad feature does not fail the whole file.** Each feature is measured inside a `try/except`, and failures become a `note` on that feature.
- **A consistent response shape.** All four measurement keys are always present, with `null` when they do not apply, so clients never have to check whether a key exists.
- **Routes are plain `def`, not `async def`.** Reading geospatial files is blocking work. FastAPI runs plain `def` routes in a thread pool, so one slow upload does not freeze the server.
- **SQLite with JSON columns** keeps setup to zero: no database server needed.

## Limitations

- **UTM has exceptions.** Southwest Norway and Svalbard use non-standard zones, and UTM is not defined beyond 84°N and 80°S. These are not handled.
- **A feature that spans several zones** is measured in the zone of its centroid, so very large features lose some accuracy.
- **Only the first Shapefile in a zip** and **only the first layer of a KML** are read. A warning is added when a zip holds several Shapefiles.
- **Processing is synchronous.** Very large files block the request until they finish.
- **No upload size limit** is enforced yet.
- **No migrations.** Tables are created with `create_all`. After a schema change, delete `geo.db` and restart.
- **No automated test suite** is included. Correctness was checked manually against the ellipsoid answer key above.
- **KML elevation (z) values** are kept in the returned geometry but ignored in measurements, which are 2D.

---

## What I learned

- **Coordinate reference systems.** Coordinates are meaningless without a CRS. Geographic CRSs use degrees, projected CRSs use meters, and every projection trades one kind of distortion for another, so the choice of projection is a choice of which error is acceptable.
- **Why measuring in degrees fails**, and why even a CRS "in meters" such as Web Mercator can be badly wrong for area.
- **File formats.** A KML is a single self-contained XML file that is always in EPSG:4326. A Shapefile is a bundle of files, holds one geometry type, and may lack its CRS.
- **Geospatial tooling.** geopandas for reading files, pyproj for transformations, and shapely for geometry and measurement.
- **FastAPI.** File uploads with `UploadFile`, dependency injection with `Depends`, response models, and error handling with `HTTPException`.
- **SQLAlchemy and Pydantic**, and why database models and API schemas are kept separate.
- **Handling failure.** Designing for corrupt files, missing CRS and unsupported geometry types, instead of only the happy path.
- **Handling Edge cases.** Handling edge cases was challenging not just in overall system but while writing specific block of code

---

## Future scope

- **Background processing** (Celery or a task queue) with a `processing` status and polling, so large uploads do not block.
- **PostGIS** instead of SQLite + JSON, enabling spatial queries and indexes.
- **An equal-area projection for polygon areas**, keeping UTM for lengths.
- **Output as a standard GeoJSON `FeatureCollection`**, and optional CSV/GeoJSON download endpoints.
- **Upload size limits** and request validation.
- **Caching pyproj transformers** per (source, target) CRS pair so they are built once per file.
- **An automated test suite** (pytest) with API tests that compare measurements with the ellipsoid answer key.
- **Docker** for one-command setup.
