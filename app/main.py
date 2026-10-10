from pathlib import Path
import uuid
import shutil
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from sqlalchemy.orm import Session
from shapely.geometry import shape
from typing import Any
import app.db.models as models
from app.db.schemas import FileInfo,MeasurementsResponse
from app.db.database import Base, engine, get_db
from app.db.schemas import FileInfo, MeasurementsResponse
from app.services.crs import CRSError, resolve_source_crs
from app.services.measure import measure_features
from app.services.reader import FileReadError, read_geo_files

Base.metadata.create_all(engine)

app = FastAPI(title="Geospatial Measurement API")

UPLOAD_DIR=Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/health")
def heatlh():
    return {"status": "ok"}

def _overall_bounds(features: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    """Bounding box around every geometry in the file (used only when the CRS is missing)."""
    boxes = [shape(f["geometry"]).bounds for f in features if f["geometry"] is not None]
    if not boxes:
        nan = float("nan")
        return (nan, nan, nan, nan)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
 
 
def _get_file_or_404(db: Session, file_id: str) -> models.File:
    db_file = db.get(models.File, file_id)
    if db_file is None:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found.")
    return db_file

@app.post("/api/files",status_code=201)
def upload_file(file: UploadFile,db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    file_id = uuid.uuid4().hex
    saved_path = UPLOAD_DIR / f"{file_id}{suffix}"
    with saved_path.open("wb") as out:
        shutil.copyfileobj(file.file,out)

    try:
        result = read_geo_files(saved_path)
        source_crs, crs_warning = resolve_source_crs(result.crs, _overall_bounds(result.features))
    except (FileReadError, CRSError) as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))

    warnings = result.warnings + ([crs_warning] if crs_warning else [])
    
    measurements = measure_features(result.features, source_crs)

    db_file = models.File(
        id=file_id,
        filename=file.filename or saved_path.name,
        status="completed",
        crs=source_crs,
        feature_count=len(result.features),
        warnings=warnings,
    )
    db_file.features = [
        models.Feature(
            index=feature["index"],
            geometry_type=feature["geometry_type"],
            geometry=feature["geometry"],
            crs=source_crs,
            properties=feature["properties"],
            **measurement,
        )
        for feature, measurement in zip(result.features, measurements)
    ]
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


@app.get("/api/files/{file_id}/", response_model=FileInfo)
def get_file(file_id: str, db: Session = Depends(get_db)):
    return _get_file_or_404(db, file_id)
 
 
@app.get("/api/files/{file_id}/measurements/", response_model=MeasurementsResponse)
def get_measurements(file_id: str, db: Session = Depends(get_db)):
    return _get_file_or_404(db, file_id)
