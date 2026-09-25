from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.services.health import HealthReport, HealthService, Status, get_health_service

router = APIRouter(tags=["infra"])


@router.get(
    "/health",
    response_model=HealthReport,
    responses={503: {"model": HealthReport, "description": "Algum componente indisponível"}},
)
async def health(
    response: Response,
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthReport:
    """Status da API e de cada dependência externa."""
    report = await service.report()
    if report.status is not Status.OK:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
