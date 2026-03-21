from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from ...models import Stock, StockBalance, StockItem, StockStatement, StockTransaction


class Command(BaseCommand):
    help = "Run inventory data quality checks for union-FK inventory integrity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-size",
            type=int,
            default=100,
            help="Max subjects to sample for balance parity checks.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit with non-zero status when hard check failures are found.",
        )

    def handle(self, *args, **options):
        sample_size = max(1, options["sample_size"])
        strict = options["strict"]

        hard_failures = []
        warnings = []

        txn_dual_set = StockTransaction.objects.filter(
            stock__isnull=False,
            stock_item__isnull=False,
        ).count()
        txn_dual_null = StockTransaction.objects.filter(
            stock__isnull=True,
            stock_item__isnull=True,
        ).count()
        stmt_dual_set = StockStatement.objects.filter(
            stock__isnull=False,
            stock_item__isnull=False,
        ).count()
        stmt_dual_null = StockStatement.objects.filter(
            stock__isnull=True,
            stock_item__isnull=True,
        ).count()

        if txn_dual_set:
            hard_failures.append(f"StockTransaction rows with both stock and stock_item set: {txn_dual_set}")
        if txn_dual_null:
            hard_failures.append(f"StockTransaction rows with neither stock nor stock_item set: {txn_dual_null}")
        if stmt_dual_set:
            hard_failures.append(f"StockStatement rows with both stock and stock_item set: {stmt_dual_set}")
        if stmt_dual_null:
            hard_failures.append(f"StockStatement rows with neither stock nor stock_item set: {stmt_dual_null}")

        legacy_unique_stocks = Stock.objects.filter(is_unique=True).count()
        if legacy_unique_stocks:
            warnings.append(
                f"Legacy Stock rows with is_unique=True: {legacy_unique_stocks} (deprecated behavioral flag)"
            )

        stock_huid_count = Stock.objects.exclude(huid__isnull=True).exclude(huid="").count()
        item_huid_count = StockItem.objects.exclude(huid__isnull=True).exclude(huid="").count()
        if stock_huid_count:
            warnings.append(
                f"Stock rows carrying HUID (consider migration to StockItem): {stock_huid_count}"
            )
        self.stdout.write(
            self.style.NOTICE(
                f"HUID coverage => Stock: {stock_huid_count}, StockItem: {item_huid_count}"
            )
        )

        mismatches = []
        sampled_stocks = list(Stock.objects.order_by("pk")[:sample_size])
        for stock in sampled_stocks:
            balance = stock.current_balance()
            try:
                view_row = StockBalance.objects.get(pk=stock.pk)
                view_qty = view_row.get_qty_bal()
                view_wt = view_row.get_wt_bal()
                if view_qty != balance["qty"] or view_wt != balance["wt"]:
                    mismatches.append(stock.pk)
            except StockBalance.DoesNotExist:
                mismatches.append(stock.pk)

        if mismatches:
            warnings.append(
                f"Stock balance projection mismatches/missing rows for sample stock IDs: {mismatches[:20]}"
            )

        physical_unreconciled = StockStatement.objects.filter(
            method="Physical",
            status=StockStatement.StatusChoices.DISCREPANCY,
        ).count()
        if physical_unreconciled:
            warnings.append(
                f"Physical statements still in discrepancy status: {physical_unreconciled}"
            )

        self.stdout.write(self.style.SUCCESS("Inventory Data Quality Report"))
        self.stdout.write(f"- Checked stock sample size: {len(sampled_stocks)}")

        if hard_failures:
            self.stdout.write(self.style.ERROR("Hard failures:"))
            for line in hard_failures:
                self.stdout.write(self.style.ERROR(f"  - {line}"))
        else:
            self.stdout.write(self.style.SUCCESS("Hard checks: PASS"))

        if warnings:
            self.stdout.write(self.style.WARNING("Warnings:"))
            for line in warnings:
                self.stdout.write(self.style.WARNING(f"  - {line}"))
        else:
            self.stdout.write(self.style.SUCCESS("Warnings: none"))

        if strict and hard_failures:
            raise CommandError("Inventory data quality check failed in strict mode.")
