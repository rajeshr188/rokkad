from django.db import migrations, models
import django.db.models.deletion


def backfill_notification_party(apps, schema_editor):
    Notification = apps.get_model("notify", "Notification")
    for notification in Notification.objects.filter(
        party__isnull=True,
        customer__party__isnull=False,
    ).select_related("customer"):
        notification.party_id = notification.customer.party_id
        notification.save(update_fields=["party"])


class Migration(migrations.Migration):

    dependencies = [
        ("notify", "0004_notificationtemplate"),
        ("party", "0005_partyportalaccess"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="party",
            field=models.ForeignKey(
                blank=True,
                help_text="Shadow Party link for the notification recipient during Customer migration.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="notifications",
                to="party.party",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["party", "status"], name="notify_noti_party_i_c28b34_idx"),
        ),
        migrations.RunPython(backfill_notification_party, migrations.RunPython.noop),
    ]
