# Generated manually for orgs architecture cleanup on 2026-06-17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orgs", "0022_companyinvitation_responded_at_and_more"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="company",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="companyownership",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="membership",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="companyinvitation",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="pendinginvitation",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="companyownership",
            constraint=models.UniqueConstraint(
                fields=("user", "company"),
                name="orgs_companyownership_unique_user_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(
                fields=("user", "company"),
                name="orgs_membership_unique_user_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="companyinvitation",
            constraint=models.UniqueConstraint(
                fields=("email", "company"),
                name="orgs_companyinvitation_unique_email_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="pendinginvitation",
            constraint=models.UniqueConstraint(
                fields=("email", "company"),
                name="orgs_pendinginvitation_unique_email_company",
            ),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("LOGIN", "User Login"),
                    ("LOGOUT", "User Logout"),
                    ("LOGIN_FAILED", "Login Failed"),
                    ("PASSWORD_CHANGE", "Password Changed"),
                    ("PASSWORD_RESET", "Password Reset"),
                    ("COMPANY_CREATE", "Company Created"),
                    ("COMPANY_UPDATE", "Company Updated"),
                    ("COMPANY_DELETE", "Company Deleted"),
                    ("COMPANY_RESTORE", "Company Restored"),
                    ("WORKSPACE_ACCESS", "Workspace Accessed"),
                    ("TEAM_INVITE", "Member Invited"),
                    ("TEAM_MEMBER_ADD", "Member Added"),
                    ("TEAM_MEMBER_REMOVE", "Member Removed"),
                    ("TEAM_ROLE_CHANGE", "Member Role Changed"),
                    ("TEAM_INVITE_ACCEPT", "Invitation Accepted"),
                    ("TEAM_INVITE_DECLINE", "Invitation Declined"),
                    ("TEAM_INVITE_REVOKE", "Invitation Revoked"),
                    ("PERMISSION_GRANT", "Permission Granted"),
                    ("PERMISSION_REVOKE", "Permission Revoked"),
                    ("PERMISSION_DENIED", "Permission Denied"),
                    ("UNAUTHORIZED_ACCESS", "Unauthorized Access Attempt"),
                    ("DATA_CREATE", "Data Created"),
                    ("DATA_UPDATE", "Data Updated"),
                    ("DATA_DELETE", "Data Deleted"),
                    ("DATA_EXPORT", "Data Exported"),
                    ("DATA_IMPORT", "Data Imported"),
                    ("BILLING_UPDATE", "Billing Updated"),
                    ("SUBSCRIPTION_CHANGE", "Subscription Changed"),
                    ("SUBSCRIPTION_CANCEL", "Subscription Cancelled"),
                    ("PAYMENT_SUCCESS", "Payment Successful"),
                    ("PAYMENT_FAILED", "Payment Failed"),
                    ("SETTINGS_UPDATE", "Settings Updated"),
                    ("PREFERENCES_UPDATE", "Preferences Updated"),
                    ("OWNERSHIP_TRANSFER", "Ownership Transferred"),
                ],
                db_index=True,
                max_length=50,
                verbose_name="Action",
            ),
        ),
    ]
