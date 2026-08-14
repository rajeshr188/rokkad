from django.db import migrations, models


GIVEN_STATUS_MAP = {
    "Created": "Draft",
    "Approved": "Approved",
    "Disbursed": "ActiveCurrent",
    "Defaulted": "ActiveNPA",
    "Auctioned": "AuctionComplete",
    "Sold": "AuctionComplete",
    "Released": "Closed",
    "Closed": "Closed",
    "Repledged": "Renewed",
    "Rejected": "Rejected",
    "Cancelled": "Cancelled",
}

TAKEN_STATUS_MAP = {
    "Created": "Draft",
    "Approved": "Draft",
    "Disbursed": "Active",
    "Released": "Closed",
    "Closed": "Closed",
    "Cancelled": "Cancelled",
    "Rejected": "Cancelled",
    "Defaulted": "Active",
    "Auctioned": "Active",
    "Sold": "Active",
    "Repledged": "Active",
    "ActiveCurrent": "Active",
    "ActiveOverdue": "Active",
    "ActiveNPA": "Active",
    "ClosurePending": "SettlementPending",
    "RenewalPending": "Active",
    "AuctionInitiated": "Active",
    "AuctionInProgress": "Active",
    "AuctionComplete": "Active",
    "Renewed": "Active",
    "WrittenOff": "Closed",
    "PendingApproval": "Draft",
    "Draft": "Draft",
}


def normalize_statuses_forward(apps, schema_editor):
    GivenLoan = apps.get_model("girvi", "GivenLoan")
    TakenLoan = apps.get_model("girvi", "TakenLoan")

    for old_status, new_status in GIVEN_STATUS_MAP.items():
        GivenLoan.objects.filter(status=old_status).update(status=new_status)

    for old_status, new_status in TAKEN_STATUS_MAP.items():
        TakenLoan.objects.filter(status=old_status).update(status=new_status)


class Migration(migrations.Migration):

    dependencies = [
        ("girvi", "0020_remove_auto_post_to_accounting"),
    ]

    operations = [
        migrations.RunPython(normalize_statuses_forward, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="givenloan",
            name="status",
            field=models.CharField(
                choices=[
                    ("Draft", "Draft"),
                    ("PendingApproval", "Pending Approval"),
                    ("Approved", "Approved"),
                    ("ActiveCurrent", "Active Current"),
                    ("ActiveOverdue", "Active Overdue"),
                    ("ActiveNPA", "Active NPA"),
                    ("ClosurePending", "Closure Pending"),
                    ("RenewalPending", "Renewal Pending"),
                    ("AuctionInitiated", "Auction Initiated"),
                    ("AuctionInProgress", "Auction In Progress"),
                    ("AuctionComplete", "Auction Complete"),
                    ("Closed", "Closed"),
                    ("Renewed", "Renewed"),
                    ("WrittenOff", "Written Off"),
                    ("Rejected", "Rejected"),
                    ("Cancelled", "Cancelled"),
                ],
                db_index=True,
                default="Draft",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="takenloan",
            name="status",
            field=models.CharField(
                choices=[
                    ("Draft", "Draft"),
                    ("Active", "Active"),
                    ("SettlementPending", "Settlement Pending"),
                    ("Closed", "Closed"),
                    ("Cancelled", "Cancelled"),
                ],
                db_index=True,
                default="Draft",
                max_length=20,
            ),
        ),
    ]
