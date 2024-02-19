from django.dispatch import receiver
from django.contrib.auth.models import User
from invitations.signals import invite_accepted
from invitations.utils import get_invitation_model
from django.contrib.auth import get_user_model
from .models import Membership
User = get_user_model()
Invitation = get_invitation_model()

@receiver(invite_accepted)
def create_membership(sender, **kwargs):
    email = kwargs.get('email')
    print(f"Signal received for email: {email}")

    invitation = Invitation.objects.filter(email=email).first()
    print(f"Invitation found: {invitation}")

    if invitation:
        user = User.objects.get(email=email)
        print(f"User found: {user}")

        if user:
            membership = Membership.objects.create(user=user, company=invitation.company)
            print(f"Membership created: {membership}")