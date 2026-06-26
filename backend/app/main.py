"""PI Vision AI - FastAPI Application."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, cameras, correlations, events, evidence, health, integrations, llm, rules, websocket
from app.config import get_settings
from app.database import engine
from app.models import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


async def _ensure_db():
    from sqlalchemy import select

    from app.core.security import get_password_hash
    from app.models import Role, User, UserRole

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            session.add(
                User(
                    email="admin@pivision.local",
                    username="admin",
                    hashed_password=get_password_hash("admin123"),
                    full_name="Administrador",
                    role=UserRole.ADMIN,
                )
            )
            for name, perms, desc in [
                ("admin", {"all": True}, "Administrador total"),
                ("supervisor", {"cameras": True, "rules": True}, "Supervisor"),
                ("operator", {"events": True}, "Operador"),
                ("readonly", {"view": True}, "Solo lectura"),
            ]:
                session.add(Role(name=name, permissions=perms, description=desc))
            await session.commit()
            logger.info("Default admin user created: admin / admin123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.snapshots_path, exist_ok=True)
    os.makedirs(settings.clips_path, exist_ok=True)
    os.makedirs(settings.logs_path, exist_ok=True)
    try:
        await _ensure_db()
    except Exception as e:
        logger.warning("DB init deferred (postgres may not be ready): %s", e)
    logger.info("PI Vision AI started - %s", settings.app_name)
    yield
    logger.info("PI Vision AI shutting down")


app = FastAPI(
    title=settings.app_name,
    description="Sistema de monitoreo inteligente de cámaras IP con IA",
    version="1.0.0-mvp",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = settings.api_prefix

app.include_router(auth.router, prefix=api_prefix)
app.include_router(cameras.router, prefix=api_prefix)
app.include_router(rules.router, prefix=api_prefix)
app.include_router(events.router, prefix=api_prefix)
app.include_router(health.router, prefix=api_prefix)
app.include_router(evidence.router, prefix=api_prefix)
app.include_router(correlations.router, prefix=api_prefix)
app.include_router(integrations.router, prefix=api_prefix)
app.include_router(llm.router, prefix=api_prefix)
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0-mvp",
        "docs": "/docs",
        "health": f"{api_prefix}/health",
    }
