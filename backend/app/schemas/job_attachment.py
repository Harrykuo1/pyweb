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
