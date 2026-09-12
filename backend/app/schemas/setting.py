from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConfigFieldResponse(BaseModel):
    """One row of admin-tunable runtime config, plus the schema metadata
    the frontend needs to render an input for it (type / bounds)."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: int
    type: Literal["int"]
    group: Literal["job", "event"]
    min: int | None = None
    max: int | None = None


class ConfigResponse(BaseModel):
    fields: list[ConfigFieldResponse]


class ConfigUpdateRequest(BaseModel):
    values: dict[str, int]
