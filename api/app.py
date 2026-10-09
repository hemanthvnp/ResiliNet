"""FastAPI app with the six endpoints of PLAN.md section 7.

Start:      uvicorn api.app:app --reload                 (port 8000; the Vite dev proxy targets it)
Mock mode:  REROUTER_MOCK=1 uvicorn api.app:app --reload  (answers from fixtures/)

Live mode runs core/sim (api/live.py); mock mode is kept for frontend work without the core.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.live import LiveBackend
from api.mock import MockBackend
from api.schemas import CompareRequest, CompareResponse, EventRequest, RunRequest, RunResponse, ScenarioInfo
from core.model.types import DecisionRecord, Snapshot

DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_app(mock: bool = False, check: bool = False) -> FastAPI:
    """`check` runs the invariant checker on every live snapshot; tests turn it on."""
    app = FastAPI(title="Network Rerouter API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["X-Mock"])
    backend = MockBackend() if mock else LiveBackend(check)

    if mock:
        @app.middleware("http")
        async def mark_mock(request, call_next):
            response = await call_next(request)
            response.headers["X-Mock"] = "true"
            return response

    @app.get("/scenarios", response_model=list[ScenarioInfo])
    def list_scenarios():
        return backend.scenarios()

    @app.post("/runs", response_model=RunResponse)
    def create_run(req: RunRequest):
        return backend.create_run(req)

    @app.post("/runs/{run_id}/events", response_model=Snapshot)
    def apply_event(run_id: str, event: EventRequest):
        return backend.apply_event(run_id, event)

    @app.post("/runs/{run_id}/reset", response_model=Snapshot)
    def reset_run(run_id: str):
        return backend.reset(run_id)

    @app.post("/compare", response_model=CompareResponse)
    def compare(req: CompareRequest):
        return backend.compare(req)

    @app.get("/runs/{run_id}/flows/{flow_id}/decision", response_model=DecisionRecord)
    def flow_decision(run_id: str, flow_id: str):
        return backend.decision(run_id, flow_id)

    return app


app = create_app(mock=os.environ.get("REROUTER_MOCK") == "1")
