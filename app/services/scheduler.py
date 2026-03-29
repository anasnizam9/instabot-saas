import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.services.automation_engine import run_enabled_rules_global
from app.services.post_publisher import cleanup_old_webhook_events, process_due_posts, recover_stuck_posts

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_publish_job() -> None:
    try:
        processed = await process_due_posts()
        if processed:
            logger.info("Processed %s due scheduled posts", processed)
    except Exception:  # noqa: BLE001
        logger.exception("Scheduled post publishing job failed")


async def _run_stuck_recovery_job() -> None:
    try:
        recovered = await recover_stuck_posts()
        if recovered:
            logger.warning("Recovered %s stuck publishing posts", recovered)
    except Exception:  # noqa: BLE001
        logger.exception("Stuck publishing recovery job failed")


async def _run_webhook_cleanup_job() -> None:
    try:
        deleted = await cleanup_old_webhook_events()
        if deleted:
            logger.info("Deleted %s old webhook idempotency entries", deleted)
    except Exception:  # noqa: BLE001
        logger.exception("Webhook cleanup job failed")


async def _run_automation_job() -> None:
    try:
        processed = await run_enabled_rules_global()
        if processed:
            logger.info("Executed %s automation rules", processed)
    except Exception:  # noqa: BLE001
        logger.exception("Automation execution job failed")


def start_scheduler() -> None:
    global _scheduler

    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled via settings")
        return

    if _scheduler and _scheduler.running:
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_publish_job,
        trigger="interval",
        seconds=settings.scheduler_interval_seconds,
        id="publish_due_posts",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_stuck_recovery_job,
        trigger="interval",
        seconds=settings.scheduler_stuck_check_interval_seconds,
        id="recover_stuck_posts",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_webhook_cleanup_job,
        trigger="interval",
        hours=settings.scheduler_cleanup_interval_hours,
        id="cleanup_webhook_events",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_automation_job,
        trigger="interval",
        seconds=settings.scheduler_automation_interval_seconds,
        id="run_automation_rules",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started with %ss interval", settings.scheduler_interval_seconds)


def stop_scheduler() -> None:
    global _scheduler

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    _scheduler = None


def is_scheduler_running() -> bool:
    return bool(_scheduler and _scheduler.running)
