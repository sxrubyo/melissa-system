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
            # Weekly report every Monday at 9am
            _scheduler.add_job(
                _send_weekly_report,
                CronTrigger(day_of_week="mon", hour=9, minute=0),
                args=[iid],
                id=f"weekly_report_{iid}",
                replace_existing=True,
            )
            log.info(f"[cron] consolidation (Sun 3am) + weekly report (Mon 9am) scheduled for {iid}")

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


async def _send_weekly_report(instance_id: str):
    """Send weekly report to admin."""
    try:
        from melissa_weekly_report import generate_weekly_report
        report = await generate_weekly_report(instance_id)
        log.info(f"[cron] weekly report generated for {instance_id}")
        # TODO: wire send_fn when admin_jid is available in cron context
    except Exception as e:
        log.error(f"[cron] weekly report failed: {e}")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("[cron] scheduler stopped")
