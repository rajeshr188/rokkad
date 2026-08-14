# Generated migration for Series guardrails

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('girvi', '0008_remove_loanchangelog_loan_loanchangelog_content_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='series',
            name='loan_count_threshold',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Max number of active loans allowed in this series. Leave blank for unlimited.',
                null=True,
                verbose_name='Loan Count Threshold',
            ),
        ),
        migrations.AddField(
            model_name='series',
            name='loan_amount_threshold',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Max total loan amount allowed in this series. Leave blank for unlimited.',
                max_digits=15,
                null=True,
                verbose_name='Loan Amount Threshold (₹)',
            ),
        ),
        migrations.AddField(
            model_name='series',
            name='deactivation_rule',
            field=models.CharField(
                choices=[
                    ('NONE', 'No Deactivation'),
                    ('LOANS', 'Disable Loans Only'),
                    ('RELEASES', 'Disable Releases Only'),
                    ('BOTH', 'Disable Loans & Releases'),
                ],
                default='NONE',
                help_text='What to disable when threshold is exceeded',
                max_length=10,
                verbose_name='Deactivation Rule',
            ),
        ),
        migrations.AddField(
            model_name='series',
            name='deactivated_for_loans',
            field=models.BooleanField(
                default=False,
                help_text='Series cannot create new loans',
                verbose_name='Deactivated for Loans',
            ),
        ),
        migrations.AddField(
            model_name='series',
            name='deactivated_for_releases',
            field=models.BooleanField(
                default=False,
                help_text='Series cannot create new releases',
                verbose_name='Deactivated for Releases',
            ),
        ),
        migrations.AddField(
            model_name='series',
            name='deactivation_date',
            field=models.DateTimeField(
                blank=True,
                help_text='When the series was deactivated due to threshold breach',
                null=True,
                verbose_name='Deactivation Date',
            ),
        ),
        migrations.AddField(
            model_name='series',
            name='threshold_exceeded_reason',
            field=models.CharField(
                blank=True,
                help_text='Which threshold was exceeded and triggered deactivation',
                max_length=255,
                verbose_name='Threshold Exceeded Reason',
            ),
        ),
        migrations.AddIndex(
            model_name='series',
            index=models.Index(
                fields=['is_active', 'deactivated_for_loans'],
                name='girvi_series_active_loans_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='series',
            index=models.Index(
                fields=['is_active', 'deactivated_for_releases'],
                name='girvi_series_active_releases_idx',
            ),
        ),
    ]
