from dataclasses import dataclass

from django.db import transaction
from django.db.models import Max
from django_tenants.utils import get_public_schema_name, schema_context

from apps.orgs.audit import AuditLog

from apps.tenant_apps.loans.domain import (
    LoanAmortisationMethod,
    LoanExtraPaymentRule,
    LoanPaymentFrequency,
    LoanProductVersionStatus,
    LoanRepaymentStructure,
)
from apps.tenant_apps.loans.models import (
    LoanProduct,
    LoanProductVersion,
    current_tenant_workspace_id,
)


class LoanProductCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class DefaultProductDefinition:
    code: str
    name: str
    repayment_structure: LoanRepaymentStructure
    amortisation_method: LoanAmortisationMethod
    payment_frequency: LoanPaymentFrequency
    extra_payment_rule: LoanExtraPaymentRule


DEFAULT_PRODUCTS = (
    DefaultProductDefinition(
        "GOLD-BULLET",
        "Single-payment bullet",
        LoanRepaymentStructure.SINGLE_PAYMENT_BULLET,
        LoanAmortisationMethod.NONE,
        LoanPaymentFrequency.AT_MATURITY,
        LoanExtraPaymentRule.NOT_APPLICABLE,
    ),
    DefaultProductDefinition(
        "GOLD-INTEREST-BULLET",
        "Periodic-interest bullet",
        LoanRepaymentStructure.PERIODIC_INTEREST_BULLET,
        LoanAmortisationMethod.NONE,
        LoanPaymentFrequency.MONTHLY,
        LoanExtraPaymentRule.NOT_APPLICABLE,
    ),
    DefaultProductDefinition(
        "GOLD-FLEXIBLE",
        "Flexible partial-payment loan",
        LoanRepaymentStructure.FLEXIBLE_PARTIAL_PAYMENT,
        LoanAmortisationMethod.NONE,
        LoanPaymentFrequency.FLEXIBLE,
        LoanExtraPaymentRule.REDUCE_PRINCIPAL,
    ),
    DefaultProductDefinition(
        "GOLD-INSTALLMENT-EMI",
        "Installment loan (EMI)",
        LoanRepaymentStructure.INSTALLMENT,
        LoanAmortisationMethod.EMI,
        LoanPaymentFrequency.MONTHLY,
        LoanExtraPaymentRule.KEEP_PAYMENT_SHORTEN_TENURE,
    ),
)


@transaction.atomic
def seed_default_loan_products(*, actor=None, request=None):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise LoanProductCatalogError("Product seeding requires an active tenant schema.")
    versions = []
    for definition in DEFAULT_PRODUCTS:
        product, _ = LoanProduct.objects.get_or_create(
            workspace_id=workspace_id,
            code=definition.code,
            defaults={
                "name": definition.name,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        version, version_created = LoanProductVersion.objects.get_or_create(
            product=product,
            version=1,
            defaults={
                "status": LoanProductVersionStatus.DRAFT.value,
                "repayment_structure": definition.repayment_structure.value,
                "amortisation_method": definition.amortisation_method.value,
                "payment_frequency": definition.payment_frequency.value,
                "minimum_tenor_months": 1,
                "maximum_tenor_months": 12,
                "operational_grace_days": 3,
                "extra_payment_rule": definition.extra_payment_rule.value,
                "calculation_contract_version": "RBI-GOLD-V1",
                "created_by": actor,
            },
        )
        if version_created:
            _audit_product_status(version, actor=actor, request=request, action="SEEDED")
        versions.append(version)
    return tuple(versions)


@transaction.atomic
def activate_product_version(version_id, *, actor=None, request=None):
    workspace_id = current_tenant_workspace_id()
    try:
        version = LoanProductVersion.objects.select_for_update().select_related("product__workspace").get(
            pk=version_id, product__workspace_id=workspace_id
        )
    except LoanProductVersion.DoesNotExist as exc:
        raise LoanProductCatalogError("Product version was not found in the active workspace.") from exc
    if version.status == LoanProductVersionStatus.ACTIVE.value:
        return version
    if version.status != LoanProductVersionStatus.DRAFT.value:
        raise LoanProductCatalogError("Only a draft product version can be activated.")
    if LoanProductVersion.objects.filter(product=version.product, status=LoanProductVersionStatus.ACTIVE.value).exclude(pk=version.pk).exists():
        raise LoanProductCatalogError("Retire the product's current active version before activating another.")
    if not version.product.is_active:
        version.product.is_active = True
        version.product.updated_by = actor
        version.product.save(update_fields=("is_active", "updated_by", "updated_at"))
    version.status = LoanProductVersionStatus.ACTIVE.value
    version.save(update_fields=("status",))
    _audit_product_status(version, actor=actor, request=request, action="ACTIVATED")
    return version


@transaction.atomic
def retire_product_version(version_id, *, actor=None, request=None):
    workspace_id = current_tenant_workspace_id()
    try:
        version = LoanProductVersion.objects.select_for_update().select_related("product__workspace").get(
            pk=version_id, product__workspace_id=workspace_id
        )
    except LoanProductVersion.DoesNotExist as exc:
        raise LoanProductCatalogError("Product version was not found in the active workspace.") from exc
    if version.status == LoanProductVersionStatus.RETIRED.value:
        return version
    if version.status != LoanProductVersionStatus.ACTIVE.value:
        raise LoanProductCatalogError("Only an active product version can be retired.")
    version.status = LoanProductVersionStatus.RETIRED.value
    version.save(update_fields=("status",))
    _audit_product_status(version, actor=actor, request=request, action="RETIRED")
    return version


@transaction.atomic
def create_product_version_draft(product_id, *, actor=None, request=None, **terms):
    workspace_id = current_tenant_workspace_id()
    try:
        product = LoanProduct.objects.select_for_update().select_related("workspace").get(
            pk=product_id, workspace_id=workspace_id
        )
    except LoanProduct.DoesNotExist as exc:
        raise LoanProductCatalogError("Loan product was not found in the active workspace.") from exc
    if product.versions.filter(status=LoanProductVersionStatus.DRAFT.value).exists():
        raise LoanProductCatalogError("Review the existing draft before creating another version.")
    next_version = (product.versions.aggregate(value=Max("version"))["value"] or 0) + 1
    version = LoanProductVersion.objects.create(
        product=product, version=next_version,
        status=LoanProductVersionStatus.DRAFT.value, created_by=actor, **terms
    )
    _audit_product_status(version, actor=actor, request=request, action="CREATED")
    return version


def _audit_product_status(version, *, actor, request, action):
    workspace = version.product.workspace
    with schema_context(get_public_schema_name()):
        AuditLog.log(
            "SETTINGS_UPDATE", user=actor, company=workspace,
            description=f"{action.title()} loan product {version.product.code} v{version.version}.",
            data={"entity": "loan_product_version", "product_id": version.product_id, "version_id": version.pk, "version": version.version, "status": version.status, "action": action},
            request=request, success=True,
        )
