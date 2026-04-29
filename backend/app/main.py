from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import auth as auth_router
from app.routers import jobs as jobs_router
from app.routers import members as members_router
from app.routers import settings as settings_router

app = FastAPI(title="pyweb backend")

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
    https_only=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router.router)
app.include_router(members_router.router)
app.include_router(jobs_router.router)
app.include_router(settings_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
