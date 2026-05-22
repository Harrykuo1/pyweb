from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
