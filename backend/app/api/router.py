from fastapi import APIRouter

from app.api.v1 import auth, datasets, groups, permissions, query

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(datasets.router)
api_router.include_router(permissions.router)
api_router.include_router(groups.router)
api_router.include_router(query.router)
