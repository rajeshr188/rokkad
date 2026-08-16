import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.dispatch import receiver
from invitations.signals import invite_accepted
from invitations.utils import get_invitation_model
from allauth.account.signals import user_signed_up
from .models import Membership, PendingInvitation
from .services import control_plane

logger = logging.getLogger(__name__)

User = get_user_model()
Invitation = get_invitation_model()


@receiver(invite_accepted)
def create_membership(sender, **kwargs):
    email = kwargs.get("email")
    invitation = kwargs.get("invitation")
    if not invitation or not email:
        return

    user = User.objects.filter(email__iexact=email).first()

    if user:
        try:
            control_plane.create_membership(
                user=user,
                company=invitation.company,
                role=invitation.role,
                request=None,
                invite_reason="invitation_accept",
            )
        except ValidationError:
            logger.warning(
                "Skipping membership create for invitation %s due to workspace seat limit",
                getattr(invitation, "id", None),
            )
        return

    # Invite accepted before account exists: stage membership intent.
    PendingInvitation.objects.get_or_create(
        email=email,
        company=invitation.company,
        defaults={"role": invitation.role},
    )


@receiver(user_signed_up)
def create_membership_on_signup(sender, **kwargs):
    user = kwargs.get("user")
    if not user or not user.email:
        return

    pending_invitations = list(
        PendingInvitation.objects.filter(email__iexact=user.email).select_related(
            "company", "role"
        )
    )
    if not pending_invitations:
        return

    with transaction.atomic():
        for pending_invitation in pending_invitations:
            try:
                control_plane.create_membership(
                    user=user,
                    company=pending_invitation.company,
                    role=pending_invitation.role,
                    request=None,
                    invite_reason="pending_invitation_signup",
                )
                pending_invitation.delete()
            except ValidationError:
                logger.warning(
                    "Keeping pending invitation %s because seat limit blocks membership create",
                    getattr(pending_invitation, "id", None),
                )
