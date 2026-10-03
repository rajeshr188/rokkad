from apps.tenant_apps.loans.models import LoanProduct, LoanProductVersion


def prepare_test_auction_service(auction, actor, prepared_on):
    """Exercise real postal-review commands with fictional evidence, never bypass the gate."""
    from datetime import datetime, time, timedelta
    from io import BytesIO
    from unittest.mock import patch
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.utils import timezone
    from reportlab.pdfgen import canvas
    from apps.tenant_apps.loans.services.statutory_notices import prepare_catalogue, record_handling
    def now(day):
        return timezone.make_aware(datetime.combine(day, time(10)))
    def attachment():
        stream = BytesIO()
        pdf = canvas.Canvas(stream)
        pdf.drawString(40, 750, 'Fictional auction evidence, test only')
        pdf.save()
        return SimpleUploadedFile('evidence.pdf', stream.getvalue())
    with patch('django.utils.timezone.now', return_value=now(prepared_on)):
        prepare_catalogue(auction.pk, actor=actor, data={
            'request_key': 'test-catalogue', 'business_name': 'Fictional lender', 'business_address': 'Fictional address',
            'borrower_address': 'Fictional borrower address', 'auctioneer_name': 'Fictional auctioneer',
            'auctioneer_reference': 'TEST-APPROVAL', 'sale_time': '10:00', 'sale_place': 'Fictional hall', 'reviewed': True})
    steps = [('PRINTED', 0, {}), ('POSTED', 0, {'article_number': 'TEST123', 'postal_service': 'RPAD', 'posted_by': 'Fictional auctioneer'}),
        ('ACKNOWLEDGED', 3, {'delivered_on': prepared_on + timedelta(days=2)}),
        ('REVIEWED', 15, {'authority_reference': 'TEST permission', 'permission_expires_on': auction.scheduled_date,
            'first_publication_on': prepared_on + timedelta(days=7), 'second_publication_on': prepared_on + timedelta(days=10),
            'police_sent_on': prepared_on + timedelta(days=7), 'legal_review_reference': 'TEST current-rule review',
            'permission_checked': True, 'publication_checked': True, 'authority_checked': True, 'valuation_checked': True, 'service_checked': True})]
    for kind, offset, extra in steps:
        day = prepared_on + timedelta(days=offset)
        with patch('django.utils.timezone.now', return_value=now(day)):
            record_handling(auction.pk, kind=kind, actor=actor,
                data={'request_key': kind, 'occurred_on': day, 'notes': 'Fictional test evidence', **extra},
                attachment=attachment() if kind != 'PRINTED' else None)


def ensure_test_product_version(workspace):
    """Return a deterministic contract fixture for tests that create loans directly."""
    product, _ = LoanProduct.objects.get_or_create(
        workspace=workspace,
        code="TEST-CONTRACT",
        defaults={"name": "Test loan contract"},
    )
    version, _ = LoanProductVersion.objects.get_or_create(
        product=product,
        version=1,
        defaults={
            "status": "ACTIVE",
            "repayment_structure": "SINGLE_PAYMENT_BULLET",
            "amortisation_method": "NONE",
            "payment_frequency": "AT_MATURITY",
            "minimum_tenor_months": 1,
            "maximum_tenor_months": 600,
            "operational_grace_days": 3,
            "extra_payment_rule": "NOT_APPLICABLE",
            "calculation_contract_version": "TEST-V1",
        },
    )
    return version
