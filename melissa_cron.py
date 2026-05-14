"""
melissa_cron.py — Scheduled tasks for Melissa (memory consolidation, cleanup).
"""
from __future__ import annotations
import logging, asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger("melissa.cron")

_scheduler: AsyncIOScheduler = None


def init_scheduler(memory_engine=None, instance_ids: list = None):
    """Initialize the cron scheduler. Call during app startup."""
    global _scheduler
    if _scheduler:
        return _scheduler

    _scheduler = AsyncIOScheduler()

    if memory_engine and instance_ids:
        for iid in instance_ids:
            _scheduler.add_job(
                _run_consolidation,
                CronTrigger(day_of_week="sun", hour=3, minute=0),
                args=[memory_engine, iid],
                id=f"consolidation_{iid}",
                replace_existing=True,
            )
            log.info(f"[cron] weekly consolidation scheduled for {iid} (Sun 3am)")

    _scheduler.start()
    log.info("[cron] scheduler started")
    return _scheduler


async def _run_consolidation(memory_engine, instance_id: str):
    """Run weekly memory consolidation for an instance."""
    try:
        await memory_engine.weekly_consolidation(instance_id)
        log.info(f"[cron] consolidation complete: {instance_id}")
    except Exception as e:
        log.error(f"[cron] consolidation failed for {instance_id}: {e}")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("[cron] scheduler stopped")
