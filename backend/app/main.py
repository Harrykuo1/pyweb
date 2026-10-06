from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.core.activity_body_limit import ActivityBodyLimitMiddleware
from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import activity as activity_router
from app.routers import auth as auth_router
from app.routers import event_comments as event_comments_router
from app.routers import event_likes as event_likes_router
from app.routers import event_photos as event_photos_router
from app.routers import event_videos as event_videos_router
from app.routers import events as events_router
from app.routers import internal as internal_router
from app.routers import job_attachments as job_attachments_router
from app.routers import job_comments as job_comments_router
from app.routers import job_likes as job_likes_router
from app.routers import jobs as jobs_router
from app.routers import members as members_router
from app.routers import settings as settings_router
from app.routers import stats as stats_router
from app.routers import timeline as timeline_router

# Security headers for every backend response. script-src 'none' neutralizes
# any HTML/JS that reaches the browser as a document (e.g. a spoofed
# attachment opened top-level) without restricting image/PDF rendering or
# same-origin embedding (frame-ancestors 'self' keeps the in-app PDF <embed>
# working). Defense-in-depth on top of the per-endpoint content-type
# normalization.
_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (
        b"content-security-policy",
        b"script-src 'none'; object-src 'none'; base-uri 'none'; "
        b"frame-ancestors 'self'",
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"SAMEORIGIN"),
    (b"referrer-policy", b"no-referrer"),
]


class SecurityHeadersMiddleware:
    """Pure-ASGI so it never buffers streaming FileResponse downloads
    (which BaseHTTPMiddleware would). Adds each header only if the response
    didn't already set it."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {k.lower() for k, _ in headers}
                for key, value in _SECURITY_HEADERS:
                    if key not in present:
                        headers.append((key, value))
            await send(message)

        await self.app(scope, receive, send_wrapper)


app = FastAPI(title="pyweb backend")

app.add_middleware(ActivityBodyLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Wire the per-IP limiter into FastAPI. slowapi reads `app.state.limiter`
# so its decorators can find the same instance the handler is configured
# against.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.session_secure,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(activity_router.router)
app.include_router(auth_router.router)
app.include_router(members_router.router)
app.include_router(jobs_router.router)
app.include_router(job_attachments_router.router)
app.include_router(job_comments_router.router)
app.include_router(job_likes_router.router)
app.include_router(event_videos_router.router)
app.include_router(events_router.router)
app.include_router(event_photos_router.router)
app.include_router(event_comments_router.router)
app.include_router(event_likes_router.router)
app.include_router(timeline_router.router)
app.include_router(stats_router.router)
app.include_router(settings_router.router)
app.include_router(internal_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
