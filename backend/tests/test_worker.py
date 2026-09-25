from app.workers.celery_app import QUEUES, celery_app
from app.workers.tasks.ping import ping


def test_filas_declaradas() -> None:
    nomes = {q.name for q in celery_app.conf.task_queues}
    assert nomes == {"celery", *QUEUES}
    assert set(QUEUES) == {"validation", "ocr", "reports", "maintenance"}


def test_ping_roteado_para_manutencao() -> None:
    rota = celery_app.amqp.router.route({}, ping.name)
    assert rota["queue"].name == "maintenance"


def test_ping_executa() -> None:
    assert ping.apply(args=("teste",)).get() == "pong (teste)"
