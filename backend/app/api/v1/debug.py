"""Rotas de diagnóstico — registradas SOMENTE em ambiente local/test."""

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.workers.tasks.ping import ping

router = APIRouter(prefix="/_debug", tags=["debug"])


class TaskEnqueued(BaseModel):
    task_id: str


@router.post("/ping-worker", status_code=status.HTTP_202_ACCEPTED, response_model=TaskEnqueued)
def ping_worker() -> TaskEnqueued:
    """Enfileira a task `ping` para comprovar a integração API → Redis → worker."""
    result = ping.delay("api")
    return TaskEnqueued(task_id=result.id)
