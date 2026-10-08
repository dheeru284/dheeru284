from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import deals, health, products, retailers, stats
from app.config.settings import get_settings
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level)
    app = FastAPI(title="Deal Engine", version="1.0.0",
                  description="Historical-price deal detection across Indian e-commerce retailers.")
    for r in (health.router, products.router, deals.router, retailers.router, stats.router):
        app.include_router(r)
    return app


app = create_app()
