import apps.tenant_apps.loans.models.intake
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0049_allow_draft_collateral_evidence_deletion'),
        ('orgs', '0024_alter_auditlog_action'),
        ('party', '0005_partyportalaccess'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CollateralIntakeBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('reference', models.CharField(max_length=32)),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('CONVERTED', 'Converted'), ('ABANDONED', 'Abandoned')], db_index=True, default='OPEN', max_length=16)),
                ('version', models.PositiveIntegerField(default=1)),
                ('abandonment_reason', models.TextField(blank=True)),
                ('abandoned_item_count', models.PositiveIntegerField(default=0)),
                ('abandoned_photo_count', models.PositiveIntegerField(default=0)),
                ('converted_at', models.DateTimeField(blank=True, null=True)),
                ('abandoned_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('abandoned_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collateral_intakes_abandoned', to=settings.AUTH_USER_MODEL)),
                ('converted_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collateral_intakes_converted', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collateral_intakes_created', to=settings.AUTH_USER_MODEL)),
                ('party', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='collateral_intakes', to='party.party')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collateral_intakes_updated', to=settings.AUTH_USER_MODEL)),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='collateral_intakes', to='orgs.company')),
            ],
            options={
                'ordering': ('-created_at', '-pk'),
            },
        ),
        migrations.CreateModel(
            name='CollateralIntakeGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('loan_date', models.DateField()),
                ('tenure_months', models.PositiveIntegerField(default=3)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groups', to='loans.collateralintakebatch')),
                ('product_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='intake_groups', to='loans.loanproductversion')),
                ('resulting_loan', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='source_intake_group', to='loans.pawnloan')),
                ('series', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='intake_groups', to='loans.loanseries')),
            ],
            options={
                'ordering': ('display_order', 'pk'),
            },
        ),
        migrations.CreateModel(
            name='CollateralIntakeItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('description', models.CharField(max_length=255)),
                ('metal', models.CharField(choices=[('GOLD', 'Gold'), ('SILVER', 'Silver'), ('OTHER', 'Other')], max_length=16)),
                ('gross_weight', models.DecimalField(decimal_places=4, max_digits=14)),
                ('net_weight', models.DecimalField(decimal_places=4, max_digits=14)),
                ('purity_percentage', models.DecimalField(decimal_places=4, max_digits=7)),
                ('latest_appraised_value', models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ('allocated_principal', models.DecimalField(decimal_places=2, max_digits=18)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='loans.collateralintakebatch')),
                ('group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='items', to='loans.collateralintakegroup')),
                ('resulting_collateral', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='source_intake_item', to='loans.pawncollateralitem')),
            ],
            options={
                'ordering': ('display_order', 'pk'),
            },
        ),
        migrations.CreateModel(
            name='CollateralIntakePhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(max_length=500, upload_to=apps.tenant_apps.loans.models.intake.intake_photo_upload_to)),
                ('original_filename', models.CharField(max_length=255)),
                ('mime_type', models.CharField(max_length=100)),
                ('sha256', models.CharField(max_length=64)),
                ('byte_size', models.PositiveBigIntegerField()),
                ('captured_at', models.DateTimeField(auto_now_add=True)),
                ('captured_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collateral_intake_photos', to=settings.AUTH_USER_MODEL)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='loans.collateralintakeitem')),
            ],
            options={
                'ordering': ('captured_at', 'pk'),
            },
        ),
        migrations.AddConstraint(
            model_name='collateralintakebatch',
            constraint=models.UniqueConstraint(fields=('workspace', 'reference'), name='loans_intake_workspace_ref_uniq'),
        ),
        migrations.AddConstraint(
            model_name='collateralintakegroup',
            constraint=models.UniqueConstraint(fields=('batch', 'name'), name='loans_intake_group_name_uniq'),
        ),
    ]
