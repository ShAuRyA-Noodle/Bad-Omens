"""RQ worker entrypoint.

Run with:

    python -m worker.main

or, inside the worker container (the compose CMD):

    CMD ["python", "-m", "worker.main"]

This process:
    * Connects to Redis using sync ``redis.Redis``.
    * Pops jobs off the ``relict_jobs`` queue.
    * Loads the target function ``worker.pipeline.run_job`` by dotted
      path and executes it.
    * Exits cleanly on SIGTERM.
"""
from __future__ import annotations

import signal
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.queue import JOB_QUEUE_NAME, get_sync_redis
from rq import SimpleWorker, Worker
from rq.queue import Queue


def main() -> int:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    log = get_logger("worker")

    redis_conn = get_sync_redis()
    queues = [Queue(JOB_QUEUE_NAME, connection=redis_conn)]

    # Prefer the regular Worker (fork-based) on Linux; fall back to the
    # SimpleWorker on platforms without fork() (e.g. Windows CI).
    worker_cls: type[Worker] | type[SimpleWorker] = (
        Worker if hasattr(signal, "SIGCHLD") else SimpleWorker
    )
    worker = worker_cls(queues, connection=redis_conn)

    log.info(
        "worker.started",
        queue=JOB_QUEUE_NAME,
        worker_class=worker_cls.__name__,
        environment=settings.ENVIRONMENT,
    )
    worker.work(with_scheduler=False, logging_level=settings.LOG_LEVEL)
    log.info("worker.stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
