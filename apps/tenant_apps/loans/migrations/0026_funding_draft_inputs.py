import decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


CANCELLATION_GUARD_SQL = r"""
CREATE TRIGGER loans_funding_cancellation_immutable
BEFORE UPDATE OR DELETE ON loans_fundingloancancellation
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();
"""

CANCELLATION_GUARD_REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS loans_funding_cancellation_immutable
ON loans_fundingloancancellation;
"""


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("loans", "0025_funding_custody_reversal_guards"),
    ]

    operations = [
        migrations.CreateModel(
            name="FundingLoanCancellation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="funding_loan_cancellations", to=settings.AUTH_USER_MODEL)),
                ("funding_loan", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="cancellation", to="loans.fundingloan")),
            ],
        ),
        migrations.CreateModel(
            name="FundingLoanDraftTerms",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("principal_amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("monthly_interest_rate", models.DecimalField(decimal_places=6, max_digits=9)),
                ("activated_on", models.DateField()),
                ("maturity_on", models.DateField()),
                ("maximum_funding_ltv_ratio", models.DecimalField(decimal_places=6, default=decimal.Decimal("0.800000"), max_digits=7)),
                ("currency_quantum", models.DecimalField(decimal_places=4, default=decimal.Decimal("0.0100"), max_digits=8)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("funding_loan", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="draft_terms", to="loans.fundingloan")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="funding_draft_terms_updated", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="FundingLoanDraftCollateral",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("selected_collateral_value", models.DecimalField(decimal_places=4, max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("collateral_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="funding_draft_selections", to="loans.pawncollateralitem")),
                ("funding_loan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="draft_collateral", to="loans.fundingloan")),
            ],
            options={"ordering": ("collateral_item__loan_id", "collateral_item_id")},
        ),
        migrations.AddConstraint(
            model_name="fundingloandraftterms",
            constraint=models.CheckConstraint(condition=models.Q(("principal_amount__gt", 0), ("monthly_interest_rate__gte", 0), ("maturity_on__gte", models.F("activated_on")), ("maximum_funding_ltv_ratio__gt", 0), ("maximum_funding_ltv_ratio__lte", 1), ("currency_quantum__gt", 0)), name="loans_funding_draft_terms_valid"),
        ),
        migrations.AddConstraint(
            model_name="fundingloandraftcollateral",
            constraint=models.UniqueConstraint(fields=("funding_loan", "collateral_item"), name="loans_funding_draft_item_uniq"),
        ),
        migrations.AddConstraint(
            model_name="fundingloandraftcollateral",
            constraint=models.CheckConstraint(condition=models.Q(("selected_collateral_value__gt", 0)), name="loans_funding_draft_item_value_positive"),
        ),
        migrations.RunSQL(
            sql=CANCELLATION_GUARD_SQL,
            reverse_sql=CANCELLATION_GUARD_REVERSE_SQL,
        ),
    ]