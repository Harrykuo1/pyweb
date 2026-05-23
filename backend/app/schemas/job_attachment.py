from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    filename: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime
    # True when the backend can serve a PDF preview at the /preview
    # endpoint — set by the upload handler after OnlyOffice produces
    # a companion file. PDFs and images don't use this field (the
    # original file is itself previewable); it specifically signals
    # whether a doc/docx/ppt/pptx has been successfully converted to
    # PDF for in-page embedding.
    preview_available: bool = False


class BulkDeleteRequest(BaseModel):
    # Capped to keep a hostile or malformed client from queuing an
    # unbounded delete in a single request; the per-job count cap is
    # 50 by default so 500 is comfortable headroom.
    ids: list[int] = Field(min_length=1, max_length=500)
    # Re-auth the admin in front of the bulk delete, same as the
    # single-attachment DELETE endpoint. Without this, a forgotten
    # unlocked session could fan out a deletion across an entire job
    # in one request.
    password: str = Field(min_length=1, max_length=255)


class BulkDeleteResponse(BaseModel):
    deleted: int
