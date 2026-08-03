from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0005_pawnloaninterestaccrual"),
    ]

    operations = [
        migrations.AddField(
            model_name="pawnloanaccountingevent",
            name="reversal_of",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reversed_by_event",
                to="loans.pawnloanaccountingevent",
            ),
        ),
        migrations.AddConstraint(
            model_name="pawnloanaccountingevent",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("event_kind", "REVERSAL"),
                        ("reversal_of__isnull", False),
                    ),
                    models.Q(
                        models.Q(("event_kind", "REVERSAL"), _negated=True),
                        ("reversal_of__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="loans_event_reversal_link_valid",
            ),
        ),
    ]
