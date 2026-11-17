"""FastAPI application factory."""

from fastapi import FastAPI

from mia.api.errors import register_error_handlers
from mia.api.invocations import router as invocations_router
from mia.api.rest import router as rest_router
from mia.api.ws import router as ws_router
from mia.service import ServiceDeps


def create_app(deps: ServiceDeps) -> FastAPI:
    """Build the app; `deps` is stored in `app.state.deps` for the routes."""
    app = FastAPI(title="MIA")
    app.state.deps = deps
    register_error_handlers(app)
    app.include_router(rest_router)
    app.include_router(invocations_router)
    app.include_router(ws_router)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "Healthy"}

    return app
