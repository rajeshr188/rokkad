from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("party", "0004_partycodesequence_alter_party_party_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="PartyPortalAccess",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("INVITED", "Invited"),
                            ("ACTIVE", "Active"),
                            ("SUSPENDED", "Suspended"),
                            ("REVOKED", "Revoked"),
                        ],
                        db_index=True,
                        default="INVITED",
                        max_length=16,
                    ),
                ),
                ("invited_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "party",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="portal_access_grants",
                        to="party.party",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="party_portal_access_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Party Portal Access",
                "verbose_name_plural": "Party Portal Access Grants",
                "ordering": ("party", "user", "status"),
            },
        ),
        migrations.AddIndex(
            model_name="partyportalaccess",
            index=models.Index(fields=["user", "status"], name="party_party_user_id_627e4a_idx"),
        ),
        migrations.AddIndex(
            model_name="partyportalaccess",
            index=models.Index(fields=["party", "status"], name="party_party_party_i_b1c4aa_idx"),
        ),
        migrations.AddConstraint(
            model_name="partyportalaccess",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["INVITED", "ACTIVE", "SUSPENDED"])),
                fields=("party", "user"),
                name="party_one_live_portal_access_per_user_party",
            ),
        ),
    ]
