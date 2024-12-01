from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.dispatch import receiver
from invitations.signals import invite_accepted
from invitations.utils import get_invitation_model

from .models import Membership

User = get_user_model()
Invitation = get_invitation_model()


@receiver(invite_accepted)
def create_membership(sender, **kwargs):
    email = kwargs.get("email")
    print(f"Signal received for email: {email}")

    # invitation = Invitation.objects.filter(email=email).first()
    invitation = kwargs.get("invitation")
    print(f"Invitation found: {invitation}")

    if invitation:
        try:
            user = User.objects.get(email=email)
            print(f"User found: {user}")
            print(f"user:{user} company:{invitation.company} role: {invitation.role}")
            membership = Membership.objects.create(
                user=user, company=invitation.company, role=invitation.role
            )
            print(f"Membership created: {membership}")
        except User.DoesNotExist:
            print(f"User not found: {email}")
            # Store the invitation details in a PendingInvitation model
            PendingInvitation.objects.create(
                email=email, company=invitation.company, role=invitation.role
            )


from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from .models import Membership, PendingInvitation

# @receiver(user_signed_up)
# def create_membership_on_signup(sender, **kwargs):
#     user = kwargs.get("user")
#     print(f"Signal received for user: {user.email}")

#     invitation = Invitation.objects.filter(email=user.email, accepted=True).first()
#    # invitation = kwargs.get("invitation")
#     print(f"Invitation found: {invitation}")

#     if invitation:
#         membership = Membership.objects.create(
#             user=user, company=invitation.company, role=invitation.role
#         )
#         print(f"Membership created: {membership}")



@receiver(user_signed_up)
def create_membership_on_signup(sender, **kwargs):
    user = kwargs.get("user")
    email = user.email

    # Check for a pending invitation
    pending_invitation = PendingInvitation.objects.filter(email=email).first()
    if pending_invitation:
        # Create the membership
        Membership.objects.create(
            user=user, company=pending_invitation.company, role=pending_invitation.role
        )
        # Delete the pending invitation
        pending_invitation.delete()
