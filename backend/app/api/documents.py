from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.document_processing import (
    ExtractionError,
    StorageError,
    extract_text,
    save_upload,
)
from app.models import Document, User
from app.schemas.api import DocumentOut
from app.security.deps import get_current_user

logger = logging.getLogger("app.documents")
router = APIRouter(prefix="/api/documents", tags=["documents"])


def _owned_document(db: Session, doc_id: int, user: User) -> Document:
    doc = db.get(Document, doc_id)
    # 404 (not 403) for other users' rows so existence is not leaked.
    if doc is None or doc.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current: User = Depends(get_current_user),
) -> Document:
    data = await file.read()
    try:
        stored = save_upload(data, file.filename or "upload", settings)
        text = extract_text(data, file.filename or "upload")
    except (StorageError, ExtractionError) as exc:
        # Clear, user-facing error; no stack trace or secret leaks.
        raise HTTPException(status_code=400, detail=str(exc))

    doc = Document(
        owner_id=current.id,
        original_filename=stored.original_filename,
        stored_name=stored.stored_name,
        extension=stored.extension,
        size_bytes=stored.size_bytes,
        text_content=text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info("user=%s uploaded document=%s (%d bytes)", current.id, doc.id, doc.size_bytes)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> list[Document]:
    return list(
        db.scalars(
            select(Document).where(Document.owner_id == current.id).order_by(Document.id.desc())
        )
    )


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> Document:
    return _owned_document(db, doc_id, current)
