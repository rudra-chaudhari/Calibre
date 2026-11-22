import logging
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.planner.models import ExternalEvent

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 60


def run_job(command_name, **kwargs):
    try:
        call_command(command_name, **kwargs)
    except Exception:
        logger.exception(
            "%s failed, retrying once in %ss", command_name, RETRY_DELAY_SECONDS
        )
        time.sleep(RETRY_DELAY_SECONDS)
        call_command(command_name, **kwargs)


class Command(BaseCommand):
    help = "Run scheduled external feed syncs (initial full sync, hourly light syncs, daily full insti sync)"

    def handle(self, *args, **options):
        if not ExternalEvent.objects.exists():
            run_job("sync_cse_feed")
            run_job("sync_insti_feed", full=True)

        scheduler = BlockingScheduler()
        scheduler.add_job(
            run_job,
            IntervalTrigger(hours=1),
            args=["sync_insti_feed"],
            id="insti-light-hourly",
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            run_job,
            IntervalTrigger(hours=1),
            args=["sync_cse_feed"],
            id="cse-hourly",
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            run_job,
            CronTrigger(hour=3, minute=30),
            args=["sync_insti_feed"],
            kwargs={"full": True},
            id="insti-full-daily",
            max_instances=1,
            coalesce=True,
        )
        self.stdout.write(self.style.SUCCESS("Feed scheduler started"))
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
