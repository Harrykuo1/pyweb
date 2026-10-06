"""Admin-only integration guide and live API reference."""

import copy
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response

from app.core.deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["API documentation"])
_GUIDE = Path(__file__).resolve().parents[1] / "docs" / "api-guide.json"


@router.get("/api-docs", dependencies=[Depends(require_admin)])
def api_docs(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    spec = copy.deepcopy(request.app.openapi())
    spec["paths"] = {
        path: operations
        for path, operations in spec["paths"].items()
        if path.startswith("/api/")
    }
    return {"guide": json.loads(_GUIDE.read_text(encoding="utf-8")), "openapi": spec}
