from django.db import migrations, models
import django.db.models.deletion


def backfill_recipient_party(apps, schema_editor):
    NotificationRecipient = apps.get_model("notify_v2", "NotificationRecipient")
    for recipient in NotificationRecipient.objects.filter(
        party__isnull=True,
        customer__party__isnull=False,
    ).select_related("customer"):
        recipient.party_id = recipient.customer.party_id
        recipient.save(update_fields=["party"])


class Migration(migrations.Migration):

    dependencies = [
        ("notify_v2", "0001_initial"),
        ("party", "0005_partyportalaccess"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationrecipient",
            name="party",
            field=models.ForeignKey(
                blank=True,
                help_text="Shadow Party link for the recipient during Customer migration.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="notify_v2_recipients",
                to="party.party",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationrecipient",
            index=models.Index(fields=["party", "is_active"], name="notify_v2_n_party_i_6df4c0_idx"),
        ),
        migrations.RunPython(backfill_recipient_party, migrations.RunPython.noop),
    ]
