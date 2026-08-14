from apps.tenant_apps.loans.models import LoanProduct, LoanProductVersion


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
