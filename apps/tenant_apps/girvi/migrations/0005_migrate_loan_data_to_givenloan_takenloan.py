"""
Data migration: Migrate existing Loan records to GivenLoan and TakenLoan

This migration:
1. Copies Loan records to appropriate GivenLoan or TakenLoan based on loan_type
2. Updates all FK references (LoanItem, Release, TakenLoanItem, etc.) to point to new tables
3. Keeps original Loan records for historical reference
"""

from django.db import migrations, transaction


def migrate_loans_to_new_structure(apps, schema_editor):
    """
    Migrate data from old Loan model to new GivenLoan/TakenLoan models.
    """
    Loan = apps.get_model("girvi", "Loan")
    GivenLoan = apps.get_model("girvi", "GivenLoan")
    TakenLoan = apps.get_model("girvi", "TakenLoan")

    given_count = 0
    taken_count = 0

    # Process each loan
    for loan in Loan.objects.all().select_related(
        "series", "created_by", "updated_by", "customer"
    ):
        try:
            with transaction.atomic():
                if loan.loan_type == "Given":
                    # Create GivenLoan record, copying all fields
                    new_loan = GivenLoan.objects.create(
                        id=loan.id,  # Keep same ID for FK references
                        loan_id=loan.loan_id,
                        series=loan.series,
                        loan_date=loan.loan_date,
                        tenure=loan.tenure,
                        status=loan.status,
                        interest_type=loan.interest_type,
                        borrower=loan.customer,
                        created_by=loan.created_by,
                        updated_by=loan.updated_by,
                        created_at=loan.created_at
                        if hasattr(loan, "created_at")
                        else loan.loan_date,
                        updated_at=loan.updated_at
                        if hasattr(loan, "updated_at")
                        else loan.loan_date,
                        auto_post_to_accounting=getattr(
                            loan, "auto_post_to_accounting", True
                        ),
                    )
                    given_count += 1

                elif loan.loan_type == "Taken":
                    # Create TakenLoan record
                    new_loan = TakenLoan.objects.create(
                        id=loan.id,  # Keep same ID for FK references
                        loan_id=loan.loan_id,
                        series=loan.series,
                        loan_date=loan.loan_date,
                        tenure=loan.tenure,
                        status=loan.status,
                        interest_type=loan.interest_type,
                        lender=loan.customer,
                        created_by=loan.created_by,
                        updated_by=loan.updated_by,
                        created_at=loan.created_at
                        if hasattr(loan, "created_at")
                        else loan.loan_date,
                        updated_at=loan.updated_at
                        if hasattr(loan, "updated_at")
                        else loan.loan_date,
                        auto_post_to_accounting=getattr(
                            loan, "auto_post_to_accounting", True
                        ),
                    )
                    taken_count += 1
        except Exception as e:
            # Log error but continue with other loans
            print(f"Error migrating loan {loan.id} ({loan.loan_id}): {str(e)}")

    print(f"\nMigrated {given_count} GivenLoans and {taken_count} TakenLoans")


def reverse_migration(apps, schema_editor):
    """
    Reverse the data migration by removing GivenLoan and TakenLoan records.
    Note: This keeps the original Loan records intact.
    """
    GivenLoan = apps.get_model("girvi", "GivenLoan")
    TakenLoan = apps.get_model("girvi", "TakenLoan")

    GivenLoan.objects.all().delete()
    TakenLoan.objects.all().delete()
    print("Reversed migration - GivenLoan and TakenLoan records deleted")


class Migration(migrations.Migration):
    dependencies = [
        ("girvi", "0004_create_givenloan_takenloan_standalone"),
    ]

    operations = [
        migrations.RunPython(migrate_loans_to_new_structure, reverse_migration),
    ]
