"""FastAPI adapters over the request-scoped MissionSession facade."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import FastAPI, Path, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from amis.api_schemas import (
    DecisionTraceSchema,
    ErrorEnvelope,
    ImpactSchema,
    MetricsSchema,
    MissionEventRequest,
    MissionEventSchema,
    MissionPlanSchema,
    MissionStateSchema,
    ObservationWindowSchema,
    PlanDiffSchema,
    ReplanRequest,
    ScenarioSchema,
    StepRequest,
)
from amis.demo import build_canonical_replan_scenario
from amis.domain import Scenario
from amis.errors import (
    ConstraintViolationError,
    ErrorCode,
    InvalidEventError,
    InvalidScenarioError,
    PlanVersionConflictError,
    ResourceNotFoundError,
    SimulationStateError,
)
from amis.config import get_cors_allowed_origin_regex, get_cors_allowed_origins
from amis.repositories import MissionSessionStore, Repositories
from amis.windows import WindowProvider


ERROR_RESPONSE_DEFINITIONS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorEnvelope, "description": "Invalid scenario or event"},
    404: {"model": ErrorEnvelope, "description": "Resource not found"},
    409: {"model": ErrorEnvelope, "description": "Mission state conflict"},
    422: {"model": ErrorEnvelope, "description": "Request validation failed"},
}

ScenarioId = Annotated[str, Path(min_length=1)]
PlanId = Annotated[str, Path(min_length=1)]


def _documented_errors(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: ERROR_RESPONSE_DEFINITIONS[code] for code in status_codes}


def _error_response(
    *, code: ErrorCode, message: str, details: dict[str, Any], status_code: int
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {"error": {"code": code, "message": message, "details": details}}
        ),
    )


def create_app(
    repositories: Repositories | None = None,
    *,
    window_provider: WindowProvider | None = None,
) -> FastAPI:
    app = FastAPI(title="AMIS REST API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_cors_allowed_origins()),
        allow_origin_regex=get_cors_allowed_origin_regex(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    store = MissionSessionStore(
        repositories or Repositories.in_memory(),
        window_provider=window_provider,
    )
    app.state.repositories = store.repositories

    error_statuses = {
        InvalidScenarioError: status.HTTP_400_BAD_REQUEST,
        InvalidEventError: status.HTTP_400_BAD_REQUEST,
        ConstraintViolationError: status.HTTP_409_CONFLICT,
        ResourceNotFoundError: status.HTTP_404_NOT_FOUND,
        SimulationStateError: status.HTTP_409_CONFLICT,
        PlanVersionConflictError: status.HTTP_409_CONFLICT,
    }

    for error_type, status_code in error_statuses.items():
        async def handle_domain_error(
            request: Request,
            error: Exception,
            *,
            response_status: int = status_code,
        ) -> JSONResponse:
            del request
            return _error_response(
                code=getattr(error, "code"),
                message=str(error),
                details=dict(getattr(error, "details")),
                status_code=response_status,
            )

        app.add_exception_handler(error_type, handle_domain_error)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        if request.method == "POST" and request.url.path == "/scenarios":
            code = ErrorCode.INVALID_SCENARIO
        elif request.url.path.endswith("/events"):
            code = ErrorCode.INVALID_EVENT
        else:
            code = ErrorCode.SIMULATION_STATE_ERROR
        return _error_response(
            code=code,
            message="request validation failed",
            details={"errors": error.errors()},
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    @app.get(
        "/demo/scenario",
        response_model=ScenarioSchema,
    )
    def get_demo_scenario() -> dict[str, Any]:
        return build_canonical_replan_scenario().to_dict()

    @app.post(
        "/scenarios",
        response_model=ScenarioSchema,
        status_code=status.HTTP_201_CREATED,
        responses=_documented_errors(400, 422),
    )
    def create_scenario(request: ScenarioSchema) -> dict[str, Any]:
        scenario = Scenario.from_dict(request.model_dump(mode="json"))
        session = store.create(scenario)
        return session.get_scenario().to_dict()

    @app.get(
        "/scenarios/{scenario_id}",
        response_model=ScenarioSchema,
        responses=_documented_errors(404, 422),
    )
    def get_scenario(scenario_id: ScenarioId) -> dict[str, Any]:
        return store.load(scenario_id).get_scenario().to_dict()

    @app.post(
        "/scenarios/{scenario_id}/windows/generate",
        response_model=list[ObservationWindowSchema],
        responses=_documented_errors(404, 422),
    )
    def generate_windows(scenario_id: ScenarioId) -> list[dict[str, Any]]:
        session = store.load(scenario_id)
        windows = session.generate_windows()
        store.save(session)
        return [window.to_dict() for window in windows]

    @app.post(
        "/scenarios/{scenario_id}/plan",
        response_model=MissionPlanSchema,
        status_code=status.HTTP_201_CREATED,
        responses=_documented_errors(404, 409, 422),
    )
    def create_plan(scenario_id: ScenarioId) -> dict[str, Any]:
        session = store.load(scenario_id)
        plan = session.plan()
        store.save(session)
        return plan.to_dict()

    @app.get(
        "/scenarios/{scenario_id}/state",
        response_model=MissionStateSchema,
        responses=_documented_errors(404, 422),
    )
    def get_state(scenario_id: ScenarioId) -> dict[str, Any]:
        return store.load(scenario_id).get_state().to_dict()

    @app.post(
        "/scenarios/{scenario_id}/simulation/step",
        response_model=MissionStateSchema,
        responses=_documented_errors(404, 409, 422),
    )
    def step_simulation(
        scenario_id: ScenarioId, request: StepRequest
    ) -> dict[str, Any]:
        session = store.load(scenario_id)
        state = session.step(request.seconds)
        store.save(session)
        return state.to_dict()

    @app.post(
        "/scenarios/{scenario_id}/events",
        response_model=MissionEventSchema,
        status_code=status.HTTP_201_CREATED,
        responses=_documented_errors(400, 404, 409, 422),
    )
    def inject_event(
        scenario_id: ScenarioId, request: MissionEventRequest
    ) -> dict[str, Any]:
        session = store.load(scenario_id)
        event = session.inject_event(
            request.event_type, request.payload.model_dump(mode="json")
        )
        store.save(session)
        return event.to_dict()

    @app.get(
        "/scenarios/{scenario_id}/events",
        response_model=list[MissionEventSchema],
        responses=_documented_errors(404, 422),
    )
    def get_events(scenario_id: ScenarioId) -> list[dict[str, Any]]:
        return [event.to_dict() for event in store.load(scenario_id).get_events()]

    @app.get(
        "/scenarios/{scenario_id}/impact",
        response_model=ImpactSchema,
        responses=_documented_errors(404, 409, 422),
    )
    def get_impact(scenario_id: ScenarioId) -> dict[str, Any]:
        return store.load(scenario_id).get_last_impact().to_dict()

    @app.post(
        "/scenarios/{scenario_id}/replan",
        response_model=MissionPlanSchema,
        status_code=status.HTTP_201_CREATED,
        responses=_documented_errors(404, 409, 422),
    )
    def replan(
        scenario_id: ScenarioId, request: ReplanRequest
    ) -> dict[str, Any]:
        session = store.load(scenario_id)
        plan = session.replan(request.expected_parent_plan_id)
        store.save(
            session, expected_current_plan_id=request.expected_parent_plan_id
        )
        return plan.to_dict()

    @app.get(
        "/plans/{plan_id}",
        response_model=MissionPlanSchema,
        responses=_documented_errors(404, 422),
    )
    def get_plan(plan_id: PlanId) -> dict[str, Any]:
        session, plan = store.load_for_plan(plan_id)
        return session.get_plan_by_id(plan.id).to_dict()

    @app.get(
        "/plans/{plan_id}/metrics",
        response_model=MetricsSchema,
        responses=_documented_errors(404, 422),
    )
    def get_metrics(plan_id: PlanId) -> dict[str, Any]:
        session, plan = store.load_for_plan(plan_id)
        return session.get_metrics(plan.id).to_dict()

    @app.get(
        "/plans/{old_plan_id}/compare/{new_plan_id}",
        response_model=PlanDiffSchema,
        responses=_documented_errors(404, 422),
    )
    def compare_plans(
        old_plan_id: PlanId, new_plan_id: PlanId
    ) -> dict[str, Any]:
        return store.compare_plans(old_plan_id, new_plan_id).to_dict()

    @app.get(
        "/plans/{plan_id}/traces",
        response_model=list[DecisionTraceSchema],
        responses=_documented_errors(404, 422),
    )
    def get_traces(plan_id: PlanId) -> list[dict[str, Any]]:
        session, plan = store.load_for_plan(plan_id)
        return [trace.to_dict() for trace in session.get_traces(plan.id)]

    return app


app = create_app()
