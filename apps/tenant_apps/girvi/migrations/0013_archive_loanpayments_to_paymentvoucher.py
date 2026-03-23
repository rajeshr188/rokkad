"""
PR-5: Archive legacy LoanPayment records as draft PaymentVoucher entries.

For each LoanPayment that doesn't already have a corresponding PaymentVoucher
(matched by reference_number = "LEGACY-LP-<lp.pk>"), create a draft PaymentVoucher
so the historical data remains visible in the DEA payments UI.

Vouchers are created with posted=False (draft) so they do NOT generate journal
entries — the historical LoanPayment records were either never posted or posted
via the broken LOAN_REPAY rule.  An accountant can manually review and post them.

Reversal: no reverse migration provided — the created PaymentVouchers can be
manually deleted if the migration needs to be undone in dev/staging.
"""
from django.db import migrations


def archive_loanpayments(apps, schema_editor):
    LoanPayment = apps.get_model("girvi", "LoanPayment")
    PaymentVoucher = apps.get_model("dea", "PaymentVoucher")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # Retrieve content type for GivenLoan so we can link source_document correctly.
    try:
        given_loan_ct = ContentType.objects.get(app_label="girvi", model="givenloan")
    except ContentType.DoesNotExist:
        given_loan_ct = None

    created_count = 0
    skipped_count = 0

    for lp in LoanPayment.objects.select_related("loan").iterator():
        ref = f"LEGACY-LP-{lp.pk}"

        # Idempotent: skip if a PaymentVoucher with this reference already exists.
        if PaymentVoucher.objects.filter(reference_number=ref).exists():
            skipped_count += 1
            continue

        try:
            PaymentVoucher.objects.create(
                # payment_id must be set explicitly: save() is not called in migrations
                payment_id=ref,
                # Link to source loan via generic FK
                source_content_type=given_loan_ct,
                source_object_id=lp.loan_id,
                # MoneyField decomposes to two DB columns per field: value + currency.
                # total_amount = primary amount; amount_in_base_currency = INR equivalent
                # (exchange_rate=1 for INR loans, so both equal lp.payment_amount).
                total_amount=lp.payment_amount,
                total_amount_currency="INR",
                amount_in_base_currency=lp.payment_amount,
                amount_in_base_currency_currency="INR",
                payment_date=lp.payment_date,
                direction="RECEIPT",
                payment_type="OTHER",
                reference_number=ref,
                description=(
                    f"Migrated from LoanPayment #{lp.pk}. "
                    f"Loan: {lp.loan_id}. "
                    f"Original date: {lp.payment_date}."
                ),
                posted=False,  # Draft — no journal entry generated
            )
            created_count += 1
        except Exception as exc:
            # Non-fatal: log and continue so the migration doesn't abort.
            import sys
            print(
                f"  [archive_loanpayments] Skipping LoanPayment #{lp.pk}: {exc}",
                file=sys.stderr,
            )
            skipped_count += 1

    print(
        f"  [archive_loanpayments] Created {created_count} draft PaymentVouchers, "
        f"skipped {skipped_count}."
    )


class Migration(migrations.Migration):

    dependencies = [
        # Last girvi migration
        ("girvi", "0012_remove_loanitem_pic_field"),
        # DEA PaymentVoucher must exist
        ("dea", "0010_seed_girvi_release_vouchertype"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(
            archive_loanpayments,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
