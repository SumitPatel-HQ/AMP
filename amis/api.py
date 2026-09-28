"""FastAPI adapters over the request-scoped MissionSession facade."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Annotated, Any

from fastapi import FastAPI, Path, Query, Request, status
from pydantic import ValidationError
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
    ObservationRequestSchema,
    ObservationWindowSchema,
    PlanDiffSchema,
    ReplanRequest,
    ScenarioSchema,
    StepRequest,
    ScenarioSummarySchema,
    ScenarioPreviewSchema,
    OrbitalElementsSchema,
    TleParseRequest,
    ContactWindowSchema,
    GroundStationSchema,
    GroundTrackPointSchema,
)
from amis.examples import cloud_example, examples
from amis.domain import Scenario
from amis.orbital.elements import catalogue, from_tle
from amis.orbital.track import ground_track
from amis.orbital.validation import preview
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
from amis.windows.selection import ScenarioWindowProvider
from amis.windows.synthetic import SyntheticWindowProvider


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
    # One schema per model: the emergency payload reuses the scenario's request
    # schema as input, which would otherwise split shared names into
    # "-Input" and "-Output" variants for API clients.
    app = FastAPI(
        title="AMIS REST API",
        version="0.1.0",
        separate_input_output_schemas=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_cors_allowed_origins()),
        allow_origin_regex=get_cors_allowed_origin_regex(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    store = MissionSessionStore(
        repositories or Repositories.in_memory(),
        window_provider=window_provider or ScenarioWindowProvider(legacy=SyntheticWindowProvider()),
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
        response_model_exclude_unset=True,
    )
    def get_demo_scenario() -> dict[str, Any]:
        return cloud_example().to_dict()

    @app.get("/examples", response_model=list[ScenarioSummarySchema])
    def list_examples() -> list[dict[str, Any]]:
        return [
            {"id": key, "name": item.name, "start_time": item.start_time,
             "end_time": item.end_time, "provider": item.window_policy.provider if item.window_policy else "legacy"}
            for key, item in examples().items()
        ]

    @app.get("/examples/{example_id}", response_model=ScenarioSchema, response_model_exclude_unset=True)
    def get_example(example_id: str) -> dict[str, Any]:
        item = examples().get(example_id)
        if item is None:
            raise ResourceNotFoundError("example does not exist", details={"example_id": example_id})
        return item.to_dict()

    @app.get("/ground-stations", response_model=list[GroundStationSchema])
    def list_ground_stations() -> list[dict[str, Any]]:
        from amis.orbital.stations import station_catalogue

        return [station.to_dict() for station in station_catalogue()]

    @app.get(
        "/scenarios/{scenario_id}/contacts",
        response_model=list[ContactWindowSchema],
        responses=_documented_errors(404, 422),
    )
    def get_contacts(scenario_id: ScenarioId) -> list[dict[str, Any]]:
        """Contact windows at the mission's stations, communication outages applied."""
        return [contact.to_dict() for contact in store.load(scenario_id).get_contacts()]

    @app.get("/orbital-elements", response_model=list[OrbitalElementsSchema], response_model_exclude_unset=True)
    def list_elements() -> list[dict[str, Any]]:
        return [item.to_dict() for item in catalogue()]

    @app.get("/orbital-elements/{norad_id}", response_model=OrbitalElementsSchema, response_model_exclude_unset=True)
    def get_elements(norad_id: int) -> dict[str, Any]:
        item = next((item for item in catalogue() if item.norad_id == norad_id), None)
        if item is None:
            raise ResourceNotFoundError("orbital elements do not exist", details={"norad_id": norad_id})
        return item.to_dict()

    @app.post("/orbital-elements/parse-tle", response_model=OrbitalElementsSchema)
    def parse_tle(request: TleParseRequest) -> dict[str, Any]:
        try:
            return from_tle(request.line1, request.line2, name=request.name, retrieved_at=datetime.now(timezone.utc)).to_dict()
        except (ValueError, TypeError) as error:
            raise InvalidScenarioError(str(error)) from error

    @app.post("/scenarios/validate", response_model=ScenarioPreviewSchema, response_model_exclude_unset=True)
    def validate_scenario(body: dict[str, Any]) -> dict[str, Any]:
        try:
            request = ScenarioSchema.model_validate(body)
        except ValidationError as error:
            return {"errors": [entry["msg"] for entry in error.errors()], "warnings": [], "windows": [], "window_counts": {}}
        return preview(Scenario.from_dict(request.model_dump(mode="json")), include_track=True)

    @app.get("/scenarios", response_model=list[ScenarioSummarySchema])
    def list_scenarios() -> list[dict[str, Any]]:
        return [
            {"id": item.id, "name": item.name, "start_time": item.start_time,
             "end_time": item.end_time,
             "provider": item.window_policy.provider if item.window_policy else "legacy"}
            for item in store.repositories.scenarios.list_all()
        ]

    @app.post(
        "/scenarios",
        response_model=ScenarioSchema,
        response_model_exclude_unset=True,
        status_code=status.HTTP_201_CREATED,
        responses=_documented_errors(400, 422),
    )
    def create_scenario(request: ScenarioSchema) -> dict[str, Any]:
        scenario = Scenario.from_dict(request.model_dump(mode="json"))
        if scenario.window_policy is not None:
            result = preview(scenario)
            if result["errors"]:
                raise InvalidScenarioError("mission is invalid", details={"errors": result["errors"]})
        session = store.create(scenario)
        return session.get_scenario().to_dict()

    @app.get(
        "/scenarios/{scenario_id}",
        response_model=ScenarioSchema,
        response_model_exclude_unset=True,
        responses=_documented_errors(404, 422),
    )
    def get_scenario(scenario_id: ScenarioId) -> dict[str, Any]:
        return store.load(scenario_id).get_scenario().to_dict()

    @app.get("/scenarios/{scenario_id}/plans", response_model=list[MissionPlanSchema])
    def list_plans(scenario_id: ScenarioId) -> list[dict[str, Any]]:
        return [plan.to_dict() for plan in store.load(scenario_id).get_plans()]

    @app.get("/scenarios/{scenario_id}/ground-track", response_model=list[GroundTrackPointSchema])
    def get_ground_track(
        scenario_id: ScenarioId,
        start: datetime | None = None,
        end: datetime | None = None,
        step_s: Annotated[int, Query(ge=1, le=3600)] = 30,
        satellite_id: str | None = None,
    ) -> list[dict[str, object]]:
        scenario = store.load(scenario_id).get_scenario()
        try:
            satellite = (
                scenario.satellite_by_id(satellite_id) if satellite_id is not None else scenario.satellite
            )
        except ValueError as error:
            raise InvalidScenarioError(str(error)) from error
        if satellite.orbit is None:
            raise InvalidScenarioError("scenario has no stored orbit")
        start = start or scenario.start_time
        end = end or scenario.end_time
        if start.tzinfo is None or end.tzinfo is None or start < scenario.start_time or end > scenario.end_time or end < start:
            raise InvalidScenarioError("ground-track range must lie inside the mission")
        if (end - start).total_seconds() / step_s > 10000:
            raise InvalidScenarioError("ground-track range exceeds 10000 samples")
        return ground_track(scenario, start, end, step_s, satellite_id=satellite.id)

    @app.get(
        "/scenarios/{scenario_id}/requests",
        response_model=list[ObservationRequestSchema],
        response_model_exclude_unset=True,
        responses=_documented_errors(404, 422),
    )
    def get_requests(scenario_id: ScenarioId) -> list[dict[str, Any]]:
        # The request pool with live statuses: the scenario stays immutable, so
        # emergency arrivals and expiry are only visible here.
        return [
            request.to_dict()
            for request in store.load(scenario_id).get_request_pool()
        ]

    @app.post(
        "/scenarios/{scenario_id}/windows/generate",
        response_model=list[ObservationWindowSchema],
        response_model_exclude_unset=True,
        responses=_documented_errors(404, 422),
    )
    def generate_windows(scenario_id: ScenarioId) -> list[dict[str, Any]]:
        session = store.load(scenario_id)
        windows = session.generate_windows()
        store.save(session)
        return [window.to_dict() for window in windows]

    @app.get(
        "/scenarios/{scenario_id}/windows",
        response_model=list[ObservationWindowSchema],
        response_model_exclude_unset=True,
        responses=_documented_errors(404, 422),
    )
    def get_windows(scenario_id: ScenarioId) -> list[dict[str, Any]]:
        return [window.to_dict() for window in store.load(scenario_id).get_windows()]

    @app.post(
        "/scenarios/{scenario_id}/plan",
        response_model=MissionPlanSchema,
        status_code=status.HTTP_201_CREATED,
        responses=_documented_errors(404, 409, 422),
    )
    def create_plan(scenario_id: ScenarioId, planner: Literal["greedy", "cp_sat"] = "greedy") -> dict[str, Any]:
        session = store.load(scenario_id)
        session.select_planner(planner)
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
        response_model_exclude_unset=True,
        status_code=status.HTTP_201_CREATED,
        responses=_documented_errors(400, 404, 409, 422),
    )
    def inject_event(
        scenario_id: ScenarioId, request: MissionEventRequest
    ) -> dict[str, Any]:
        session = store.load(scenario_id)
        event_request = request.root
        event = session.inject_event(
            event_request.event_type, event_request.payload.model_dump(mode="json")
        )
        store.save(session)
        return event.to_dict()

    @app.get(
        "/scenarios/{scenario_id}/events",
        response_model=list[MissionEventSchema],
        response_model_exclude_unset=True,
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
        session.select_planner(request.planner or session.get_plan().planner_name)
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
