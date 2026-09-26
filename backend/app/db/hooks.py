"""Ações que só podem acontecer DEPOIS do commit (ex.: enfileirar uma task).

Se a task for enfileirada antes do commit, o worker pode buscar a linha antes dela
existir (ou ver dados antigos). `on_commit` agenda a ação para após o commit e a
descarta em caso de rollback.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

_KEY = "on_commit_callbacks"


def _run(session: Session) -> None:
    callbacks: list[Callable[[], Any]] = session.info.pop(_KEY, [])
    for cb in callbacks:
        cb()


def _discard(session: Session) -> None:
    session.info.pop(_KEY, None)


def on_commit(db: AsyncSession, callback: Callable[[], Any]) -> None:
    sync = db.sync_session
    if _KEY not in sync.info:
        sync.info[_KEY] = []
        if not event.contains(sync, "after_commit", _run):
            event.listen(sync, "after_commit", _run)
            event.listen(sync, "after_rollback", _discard)
    sync.info[_KEY].append(callback)
