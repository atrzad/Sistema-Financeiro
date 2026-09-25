from app.core.logging import get_logger
from app.workers.celery_app import celery_app

log = get_logger("worker")


@celery_app.task(name="app.workers.tasks.ping.ping")
def ping(origem: str) -> str:
    log.info("ping_recebido", origem=origem)
    return f"pong ({origem})"
