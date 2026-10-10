from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError, PermissionDenied
from apps.subscriptions.razorpay_service import BillingProviderError
from apps.subscriptions.unpaid_agreement import release_unused_agreement


class Command(BaseCommand):
    help = 'Retire a cancelled, never-authorized unpaid agreement and cancel its unpaid invoices.'

    def add_arguments(self, parser):
        for name in ('workspace-id', 'actor-id', 'agreement-id'):
            parser.add_argument('--' + name, type=int, required=True)
        parser.add_argument('--reason', required=True)

    def handle(self, **options):
        try:
            event = release_unused_agreement(workspace_id=options['workspace_id'],
                actor=get_user_model().objects.get(pk=options['actor_id']),
                agreement_id=options['agreement_id'], reason=options['reason'])
        except (ValidationError, PermissionDenied, BillingProviderError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'Unused agreement retired; audit event {event.pk}. Access unchanged.')
