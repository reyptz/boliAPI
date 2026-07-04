"""
BoliAPI — Point d'entrée principal.
Super-App VTC, Livraison & Marketplace — Backend souverain.
"""

import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.database import create_tables
from app.domain.exceptions import DomainException
from app.presentation.routers import auth_router, user_router


import asyncio
from app.infrastructure.rides.rabbitmq_worker import start_rabbitmq_worker
from app.infrastructure.sync.scheduler import start_sync_loop

# ── Configuration du Logging ─────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boli-api")

# ── Initialisation du Limiter (Rate Limiting) ────────────────
# Backend Redis pour partager les compteurs entre workers/instances
# (sinon chaque worker a son propre compteur, contournable en round-robin).
# Fallback en mémoire si Redis est injoignable, pour ne jamais bloquer l'API.
def _rate_limit_storage_uri() -> str:
    try:
        import redis as _sync_redis

        client = _sync_redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        client.ping()
        client.close()
        return settings.REDIS_URL
    except Exception as exc:
        logger.warning(
            "Redis injoignable (%s) — rate limiting en mémoire (non partagé).", exc
        )
        return "memory://"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60 per minute"],
    storage_uri=_rate_limit_storage_uri(),
)

# ── Lifecycle ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown hooks."""
    # Startup : créer les tables 
    await create_tables()
    
    # Lancer le worker RabbitMQ en tâche de fond
    asyncio.create_task(start_rabbitmq_worker())

    # Lancer la sync marketplace périodique (SuguJate → Postgres) en tâche de fond
    asyncio.create_task(start_sync_loop())

    print(f"\n>>> {settings.APP_NAME} v{settings.APP_VERSION} started")
    print(f"    Debug mode: {settings.DEBUG}")
    print(f"    Database: {settings.DATABASE_URL}\n")
    yield
    # Shutdown
    print(f"\n<<< {settings.APP_NAME} stopped\n")


# ── Application FastAPI ──────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API souveraine de la Super-App Boli — "
        "VTC, Livraison, Marketplace, Colis & Covoiturage (Mali)."
    ),
    lifespan=lifespan,
    # La doc interactive n'est exposée qu'en mode debug (jamais en production).
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ─────────────────────────────────────────────────────
# On ne combine JAMAIS `allow_origins=["*"]` avec `allow_credentials=True`
# (interdit par la spec CORS et dangereux). La liste blanche est configurable
# via la variable d'environnement CORS_ORIGINS (séparée par des virgules).
#
# En DEBUG uniquement, on autorise en plus tout `localhost`/`127.0.0.1` sur un
# port quelconque ainsi que `10.0.2.2` (alias de l'hôte depuis l'émulateur
# Android) via une regex — les ports des serveurs de dev Flutter/Expo web sont
# choisis dynamiquement et ne peuvent pas être listés à l'avance. Starlette
# reflète alors l'origine exacte matchée (jamais un `*`), donc la combinaison
# avec `allow_credentials=True` reste conforme à la spec CORS.
_dev_origin_regex = (
    r"^https?://(localhost|127\.0\.0\.1|10\.0\.2\.2)(:\d+)?$" if settings.DEBUG else None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=_dev_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Middlewares de Sécurité et de Logging ───────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
    )
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"Method: {request.method} | Path: {request.url.path} | "
        f"Status: {response.status_code} | Duration: {duration:.4f}s"
    )
    return response


# ── Exception handler global pour les erreurs domaine ────────
@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    """Convertit les exceptions métier en réponses HTTP."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# ── Routers ──────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(user_router.router, prefix="/api/v1")
from app.presentation.routers.ride_router import ride_router, ws_router
from app.presentation.routers.wallet_router import wallet_router
from app.presentation.routers.merchant_router import merchant_router
from app.presentation.routers.sync_router import sync_router
from app.presentation.routers.carpool_router import carpool_router
app.include_router(ride_router, prefix="/api/v1")
app.include_router(wallet_router, prefix="/api/v1")
app.include_router(merchant_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(carpool_router, prefix="/api/v1")
app.include_router(ws_router)


# ── Health check ─────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """Health check — vérifie que l'API est opérationnelle."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/health", tags=["Health"])
async def health():
    """Endpoint de health check détaillé."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug": settings.DEBUG,
    }


# ── Prometheus Instrumentation ───────────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

