from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from apps.orgs.models import Company
from ...models import (
    AssignedProductAttribute,
    AssignedVariantAttribute,
    Attribute,
    AttributeProduct,
    AttributeValue,
    AttributeVariant,
    Product,
    ProductVariant,
)


class Command(BaseCommand):
    help = "Migrate Product/ProductVariant jattributes data into normalized attribute tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help="Run for a specific tenant schema only.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report actions without writing any data.",
        )
        parser.add_argument(
            "--skip-errors",
            action="store_true",
            help="Continue processing other schemas when one schema fails.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        target_schema = options["schema"]
        skip_errors = options["skip_errors"]

        if not hasattr(Product, "jattributes") or not hasattr(ProductVariant, "jattributes"):
            self.stdout.write(
                self.style.WARNING(
                    "jattributes fields are already removed; nothing to migrate."
                )
            )
            return

        schemas = []
        if target_schema:
            schemas = [target_schema]
        else:
            schemas = list(Company.objects.values_list("schema_name", flat=True))

        if not schemas:
            self.stdout.write(self.style.WARNING("No tenant schemas found."))
            return

        self.stdout.write(
            self.style.NOTICE(
                "Starting jattributes migration to normalized tables"
                + (" (dry-run)" if dry_run else "")
            )
        )

        failures = []

        for schema_name in schemas:
            stats = {
                "products_seen": 0,
                "variants_seen": 0,
                "product_assignments_created": 0,
                "variant_assignments_created": 0,
                "values_linked": 0,
                "missing_attributes": 0,
                "missing_values": 0,
                "empty_payloads": 0,
            }

            self.stdout.write(self.style.NOTICE(f"Processing schema: {schema_name}"))

            try:
                with schema_context(schema_name):
                    with transaction.atomic():
                        self._migrate_products(stats, dry_run)
                        self._migrate_variants(stats, dry_run)

                        if dry_run:
                            transaction.set_rollback(True)

                self._print_summary(stats, dry_run, schema_name)
            except Exception as exc:
                failures.append((schema_name, str(exc)))
                self.stdout.write(
                    self.style.ERROR(f"Schema {schema_name} failed: {exc}")
                )
                if not skip_errors:
                    raise

        if failures:
            self.stdout.write(self.style.WARNING("Migration finished with failures:"))
            for schema_name, message in failures:
                self.stdout.write(f"- {schema_name}: {message}")

    def _migrate_products(self, stats, dry_run):
        queryset = Product.objects.select_related("product_type").iterator()
        for product in queryset:
            stats["products_seen"] += 1
            jattrs = product.jattributes or {}
            if not jattrs:
                stats["empty_payloads"] += 1
                continue

            for attr_name, value_name in jattrs.items():
                attribute = Attribute.objects.filter(name=attr_name).first()
                if not attribute:
                    stats["missing_attributes"] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Product {product.pk}: missing Attribute name='{attr_name}'"
                        )
                    )
                    continue

                attribute_value = AttributeValue.objects.filter(
                    attribute=attribute, name=value_name
                ).first()
                if not attribute_value:
                    stats["missing_values"] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Product "
                            f"{product.pk}: missing AttributeValue name='{value_name}' "
                            f"for Attribute '{attr_name}'"
                        )
                    )
                    continue

                assignment, _ = AttributeProduct.objects.get_or_create(
                    product_type=product.product_type,
                    attribute=attribute,
                )
                assigned, created = AssignedProductAttribute.objects.get_or_create(
                    product=product,
                    assignment=assignment,
                )
                if created:
                    stats["product_assignments_created"] += 1

                if dry_run:
                    stats["values_linked"] += 1
                else:
                    if not assigned.values.filter(pk=attribute_value.pk).exists():
                        assigned.values.add(attribute_value)
                        stats["values_linked"] += 1

    def _migrate_variants(self, stats, dry_run):
        queryset = ProductVariant.objects.select_related("product__product_type").iterator()
        for variant in queryset:
            stats["variants_seen"] += 1
            jattrs = variant.jattributes or {}
            if not jattrs:
                stats["empty_payloads"] += 1
                continue

            for attr_name, value_name in jattrs.items():
                attribute = Attribute.objects.filter(name=attr_name).first()
                if not attribute:
                    stats["missing_attributes"] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Variant {variant.pk}: missing Attribute name='{attr_name}'"
                        )
                    )
                    continue

                attribute_value = AttributeValue.objects.filter(
                    attribute=attribute, name=value_name
                ).first()
                if not attribute_value:
                    stats["missing_values"] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Variant "
                            f"{variant.pk}: missing AttributeValue name='{value_name}' "
                            f"for Attribute '{attr_name}'"
                        )
                    )
                    continue

                assignment, _ = AttributeVariant.objects.get_or_create(
                    product_type=variant.product.product_type,
                    attribute=attribute,
                )
                assigned, created = AssignedVariantAttribute.objects.get_or_create(
                    variant=variant,
                    assignment=assignment,
                )
                if created:
                    stats["variant_assignments_created"] += 1

                if dry_run:
                    stats["values_linked"] += 1
                else:
                    if not assigned.values.filter(pk=attribute_value.pk).exists():
                        assigned.values.add(attribute_value)
                        stats["values_linked"] += 1

    def _print_summary(self, stats, dry_run, schema_name):
        self.stdout.write(self.style.SUCCESS("Migration completed"))
        self.stdout.write(f"schema: {schema_name}")
        self.stdout.write(f"dry_run: {dry_run}")
        self.stdout.write(f"products_seen: {stats['products_seen']}")
        self.stdout.write(f"variants_seen: {stats['variants_seen']}")
        self.stdout.write(
            "product_assignments_created: "
            f"{stats['product_assignments_created']}"
        )
        self.stdout.write(
            "variant_assignments_created: "
            f"{stats['variant_assignments_created']}"
        )
        self.stdout.write(f"values_linked: {stats['values_linked']}")
        self.stdout.write(f"missing_attributes: {stats['missing_attributes']}")
        self.stdout.write(f"missing_values: {stats['missing_values']}")
        self.stdout.write(f"empty_payloads: {stats['empty_payloads']}")
