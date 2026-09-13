from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field

from src.geosa_rag.service import (
    ask,
    ask_with_attachment,
    build_index,
)
from src.intelligence.io import (
    extract_attachment_context,
)


router = APIRouter(
    prefix="/geosa",
    tags=["GeoSA Intelligence"],
)


class GeoSAQuestion(BaseModel):
    question: str = Field(
        min_length=2
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
    )


@router.post("/ask")
def ask_geosa(
    body: GeoSAQuestion,
):
    try:
        return ask(
            body.question,
            body.top_k,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.post("/ask-file")
async def ask_geosa_file(
    question: str = Form(...),
    top_k: int = Form(5),
    file: UploadFile = File(...),
):
    try:
        content = await file.read()

        attachment_context = (
            extract_attachment_context(
                file.filename or "attachment",
                content,
            )
        )

        return ask_with_attachment(
            question=question,
            attachment_name=(
                file.filename
                or "attachment"
            ),
            attachment_context=(
                attachment_context
            ),
            top_k=top_k,
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


@router.post("/reindex")
def reindex_geosa():
    try:
        return build_index()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc