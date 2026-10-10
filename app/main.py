from pathlib import Path
import uuid
import shutil
from fastapi import FastAPI, HTTPException, UploadFile
from app.services.reader import read_geo_files
from app.services.reader import FileReadError

app = FastAPI(title="Geospatial Measurement API")

UPLOAD_DIR=Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/health")
def heatlh():
    return {"status": "ok"}

@app.post("/api/files",status_code=201)
def upload_file(file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    file_id = uuid.uuid4().hex
    saved_path = UPLOAD_DIR / f"{file_id}{suffix}"
    with saved_path.open("wb") as out:
        shutil.copyfileobj(file.file,out)

    try:
        result = read_geo_files(saved_path)
    except FileReadError as e:
        raise HTTPException(status_code=400,detail=str(e))


    return {
        "file_id": file_id,
        "filename": file.filename,
        "crs": result.crs,
        "feature_count": len(result.features),
        "warnings": result.warnings
    }


