from starlette.responses import JSONResponse

MAX_ACTIVITY_BODY_BYTES = 1024 * 1024


class ActivityBodyLimitMiddleware:
    """Bound JSON buffering before FastAPI parses the public ingestion endpoint."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].rstrip("/") not in {
            "/api/activity/batches",
            "/api/activity/channels",
        }:
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_ACTIVITY_BODY_BYTES:
                await JSONResponse(
                    {"detail": "Activity batch exceeds 1 MiB"}, status_code=413
                )(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
