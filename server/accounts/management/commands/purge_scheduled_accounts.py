from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import AccountDeletionRequest


class Command(BaseCommand):
    help = "Permanently delete resident accounts whose recovery period has ended."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report eligible accounts without deleting them.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        eligible = AccountDeletionRequest.objects.filter(
            status=AccountDeletionRequest.Status.PENDING,
            scheduled_for__isnull=False,
            scheduled_for__lte=now,
            user__is_staff=False,
            user__is_superuser=False,
        ).select_related("user")

        count = eligible.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} resident account(s) eligible for deletion.")
            return

        deleted = 0
        for deletion in eligible.iterator():
            with transaction.atomic():
                locked = (
                    AccountDeletionRequest.objects.select_for_update()
                    .select_related("user")
                    .filter(
                        pk=deletion.pk,
                        status=AccountDeletionRequest.Status.PENDING,
                        scheduled_for__lte=timezone.now(),
                        user__is_staff=False,
                        user__is_superuser=False,
                    )
                    .first()
                )
                if locked is None:
                    continue
                locked.user.delete()
                deleted += 1

        self.stdout.write(
            self.style.SUCCESS(f"Permanently deleted {deleted} resident account(s).")
        )
