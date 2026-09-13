from __future__ import annotations

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field

from src.dataset_compare.service import (
    compare_datasets,
)
from src.georfp.service import (
    generate_geospatial_rfp,
)
from src.intelligence.io import (
    load_vector_upload,
    preview_geojson,
)
from src.poi_intelligence.service import (
    run_poi_intelligence,
)


router = APIRouter(
    prefix="/intelligence",
    tags=["Meyaar Intelligence"],
)


class GeoRFPRequest(BaseModel):
    project_description: str = Field(
        min_length=10
    )
    top_k: int = Field(
        default=8,
        ge=1,
        le=12,
    )


@router.post("/poi")
async def analyze_poi(
    file: UploadFile = File(...),
    question: str = Form(
        "حلل جودة بيانات نقاط الاهتمام."
    ),
):
    try:
        content = await file.read()

        geojson = load_vector_upload(
            file.filename or "poi.geojson",
            content,
        )

        result = run_poi_intelligence(
            geojson=geojson,
            question=question,
        )

        result["filename"] = (
            file.filename
            or "poi.geojson"
        )

        result["preview_geojson"] = (
            preview_geojson(
                geojson,
                limit=700,
            )
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.post("/compare")
async def compare_uploaded_datasets(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    try:
        content_a = await file_a.read()
        content_b = await file_b.read()

        dataset_a = load_vector_upload(
            file_a.filename
            or "dataset-a.geojson",
            content_a,
        )

        dataset_b = load_vector_upload(
            file_b.filename
            or "dataset-b.geojson",
            content_b,
        )

        return compare_datasets(
            dataset_a=dataset_a,
            dataset_b=dataset_b,
            dataset_a_name=(
                file_a.filename
                or "Dataset A"
            ),
            dataset_b_name=(
                file_b.filename
                or "Dataset B"
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.post("/georfp")
def generate_rfp(
    body: GeoRFPRequest,
):
    try:
        return generate_geospatial_rfp(
            body.project_description,
            body.top_k,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc