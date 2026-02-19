from fastapi import FastAPI

from app.api.router import api_router
from app.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="Data Sharing Platform",
        description="Data Sharing Platform API",
        version="0.1.0",
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
