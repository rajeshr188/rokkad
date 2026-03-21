"""
Inventory Movement Service Layer

Provides unified API for recording stock movements across both Stock (lots) and StockItem (unique units).
All inventory writes should flow through these service methods for consistency and audit trail.

Core responsibility: Transform domain events (purchase, sale, split, merge, audit) into atomic 
StockTransaction and StockStatement records with proper status management.
"""

from decimal import Decimal
from django.db import models, transaction
from django.db.models.functions import Coalesce

from ...models import Stock, StockItem, StockTransaction, StockStatement, Movement


class InventoryMovementService:
    """
    Centralized service for recording inventory movements.
    All direct StockTransaction creation should go through this service.
    """

    @staticmethod
    @transaction.atomic
    def record_movement(
        subject,
        movement_type_id,
        quantity,
        weight,
        journal_entry=None,
        reason=None,
        description=None
    ):
        """
        Record a single movement for a Stock or StockItem.

        Args:
            subject: Stock or StockItem instance
            movement_type_id: Movement.id (e.g., 'P', 'S', 'PR', 'SR', 'AD', 'RM', 'SS')
            quantity: Integer quantity moved
            weight: Decimal weight moved
            journal_entry: Optional JournalEntry for accounting moves
            reason: Optional reason code for audit trail
            description: Optional text description

        Returns:
            StockTransaction instance

        Raises:
            ValueError: If subject is invalid or movement parameters are invalid
            Movement.DoesNotExist: If movement_type_id is not found
        """
        if not isinstance(subject, (Stock, StockItem)):
            raise ValueError(f"Subject must be Stock or StockItem, got {type(subject)}")

        if quantity == 0 and weight == Decimal(0):
            raise ValueError("At least one of quantity or weight must be non-zero")

        # Validate movement exists
        try:
            movement = Movement.objects.get(id=movement_type_id)
        except Movement.DoesNotExist:
            raise Movement.DoesNotExist(
                f"Movement type '{movement_type_id}' not found. "
                f"Valid types: {', '.join(Movement.objects.values_list('id', flat=True))}"
            )

        # Create transaction with union FK semantics
        txn_kwargs = {
            'quantity': quantity,
            'weight': weight,
            'movement_type': movement,
            'journal_entry': journal_entry,
            'description': description or reason,
        }

        if isinstance(subject, Stock):
            txn_kwargs['stock'] = subject
        else:  # StockItem
            txn_kwargs['stock_item'] = subject

        txn = StockTransaction.objects.create(**txn_kwargs)

        # Update subject status based on new balance
        subject.update_status()

        return txn

    @staticmethod
    @transaction.atomic
    def split_lot(
        parent_stock,
        splits,
        reason=None
    ):
        """
        Split a parent lot into child lots/items with movements recorded.

        Args:
            parent_stock: Stock instance (must not be is_unique=True)
            splits: List of dicts:
                {
                    'quantity': int,
                    'weight': Decimal,
                    'is_unique': bool,  # False=Stock lot, True=StockItem unique
                    'serial_no': str (optional),
                    'huid': str (optional),
                }
            reason: Optional reason code

        Returns:
            List of created (Stock or StockItem) instances (same order as splits)

        Raises:
            ValueError: If parent is unique, balances don't match, or splits invalid
        """
        if parent_stock.is_unique:
            raise ValueError("Cannot split a unique item; only split lots")

        # Validate splits sum to parent balance
        current_balance = parent_stock.current_balance()
        splits_qty = sum(s.get('quantity', 0) for s in splits)
        splits_wt = sum(Decimal(str(s.get('weight', 0))) for s in splits)

        if splits_qty != current_balance['qty'] or splits_wt != current_balance['wt']:
            raise ValueError(
                f"Splits ({splits_qty} qty, {splits_wt} wt) do not match parent balance "
                f"({current_balance['qty']} qty, {current_balance['wt']} wt)"
            )

        created_splits = []

        for split_spec in splits:
            split_qty = split_spec['quantity']
            split_wt = Decimal(str(split_spec['weight']))
            is_unique = split_spec.get('is_unique', False)

            if is_unique:
                # Create StockItem
                child = StockItem.objects.create(
                    variant=parent_stock.variant,
                    weight=split_wt,
                    quantity=1,  # Always 1 for unique
                    purchase_touch=parent_stock.purchase_touch,
                    purchase_rate=parent_stock.purchase_rate,
                    parent_stock=parent_stock,
                    serial_no=split_spec.get('serial_no', ''),
                    huid=split_spec.get('huid', ''),
                )
                # Record inbound movement to new item
                InventoryMovementService.record_movement(
                    subject=child,
                    movement_type_id='AD',
                    quantity=1,
                    weight=split_wt,
                    reason=reason or 'SPLIT',
                    description=f'Split from {parent_stock}',
                )
            else:
                # Create Stock lot
                child = Stock.objects.create(
                    variant=parent_stock.variant,
                    weight=split_wt,
                    quantity=split_qty,
                    purchase_touch=parent_stock.purchase_touch,
                    purchase_rate=parent_stock.purchase_rate,
                    is_unique=False,
                    parent_stock=parent_stock,
                    sku=parent_stock.sku,
                )
                # Record inbound movement to new lot
                InventoryMovementService.record_movement(
                    subject=child,
                    movement_type_id='AD',
                    quantity=split_qty,
                    weight=split_wt,
                    reason=reason or 'SPLIT',
                    description=f'Split from {parent_stock}',
                )

            created_splits.append(child)

        # Record removal from parent
        InventoryMovementService.record_movement(
            subject=parent_stock,
            movement_type_id='SS',  # Split Separate
            quantity=current_balance['qty'],
            weight=current_balance['wt'],
            reason=reason or 'SPLIT',
            description=f'Split into {len(splits)} parts',
        )

        return created_splits

    @staticmethod
    @transaction.atomic
    def merge_lots(
        lots,
        reason=None
    ):
        """
        Merge multiple lots into a single new lot with movements recorded.

        Args:
            lots: List of Stock instances (cannot include unique items)
            reason: Optional reason code

        Returns:
            New Stock instance (merged lot)

        Raises:
            ValueError: If any lot is_unique or list is empty
        """
        if not lots:
            raise ValueError("Must provide at least one lot to merge")

        if any(lot.is_unique for lot in lots):
            raise ValueError("Cannot merge unique items; merge only Stock lots")

        # Get variant from first lot (validate all match)
        variant = lots[0].variant
        if not all(lot.variant == variant for lot in lots):
            raise ValueError("All lots must have the same variant")

        # Consolidate balances
        total_qty = 0
        total_wt = Decimal(0)
        for lot in lots:
            balance = lot.current_balance()
            total_qty += balance['qty']
            total_wt += balance['wt']

        # Create merged lot
        merged_lot = Stock.objects.create(
            variant=variant,
            quantity=total_qty,
            weight=total_wt,
            purchase_touch=lots[0].purchase_touch,
            purchase_rate=lots[0].purchase_rate,
            is_unique=False,
            sku=lots[0].sku,
        )

        # Record removal from all source lots
        for source_lot in lots:
            balance = source_lot.current_balance()
            InventoryMovementService.record_movement(
                subject=source_lot,
                movement_type_id='RM',  # Merge Remove
                quantity=balance['qty'],
                weight=balance['wt'],
                reason=reason or 'MERGE',
                description=f'Merged into {merged_lot}',
            )

        # Record addition to merged lot
        InventoryMovementService.record_movement(
            subject=merged_lot,
            movement_type_id='AD',  # Add
            quantity=total_qty,
            weight=total_wt,
            reason=reason or 'MERGE',
            description=f'Merged from {len(lots)} lots',
        )

        return merged_lot

    @staticmethod
    @transaction.atomic
    def create_checkpoint(
        subject,
        method='Auto'
    ):
        """
        Create a checkpoint (StockStatement) for a Stock or StockItem.

        Checkpoint captures a point-in-time balance after all prior transactions.
        Subsequent balance queries will compute from this checkpoint + new transactions.

        Args:
            subject: Stock or StockItem instance
            method: 'Auto' or 'Physical'

        Returns:
            StockStatement instance

        Raises:
            ValueError: If subject is invalid
        """
        if not isinstance(subject, (Stock, StockItem)):
            raise ValueError(f"Subject must be Stock or StockItem, got {type(subject)}")

        # Get last checkpoint
        try:
            last_stmt = subject.statements.latest()
            ls_wt = last_stmt.Closing_wt
            ls_qty = last_stmt.Closing_qty
        except StockStatement.DoesNotExist:
            last_stmt = None
            ls_wt = Decimal(0)
            ls_qty = 0

        # Get transactions since last checkpoint
        txn_qs = StockTransaction.objects.all()
        if isinstance(subject, Stock):
            txn_qs = txn_qs.filter(stock=subject)
        else:  # StockItem
            txn_qs = txn_qs.filter(stock_item=subject)

        if last_stmt:
            txn_qs = txn_qs.filter(created__gte=last_stmt.created)

        # Separate in and out movements
        in_txns = txn_qs.filter(movement_type__direction='+').aggregate(
            qty=Coalesce(models.Sum('quantity', output_field=models.IntegerField()), 0),
            wt=Coalesce(
                models.Sum('weight', output_field=models.DecimalField()),
                Decimal('0.0')
            ),
        )
        out_txns = txn_qs.filter(movement_type__direction='-').aggregate(
            qty=Coalesce(models.Sum('quantity', output_field=models.IntegerField()), 0),
            wt=Coalesce(
                models.Sum('weight', output_field=models.DecimalField()),
                Decimal('0.0')
            ),
        )

        # Compute closing balance
        closing_qty = ls_qty + (in_txns['qty'] - out_txns['qty'])
        closing_wt = ls_wt + (in_txns['wt'] - out_txns['wt'])

        # Create statement with union FK semantics
        stmt_kwargs = {
            'method': method,
            'Closing_qty': closing_qty,
            'Closing_wt': closing_wt,
            'total_qty_in': in_txns['qty'],
            'total_wt_in': in_txns['wt'],
            'total_qty_out': out_txns['qty'],
            'total_wt_out': out_txns['wt'],
        }

        if isinstance(subject, Stock):
            stmt_kwargs['stock'] = subject
        else:  # StockItem
            stmt_kwargs['stock_item'] = subject

        stmt = StockStatement.objects.create(**stmt_kwargs)

        return stmt

    @staticmethod
    def get_balance(subject):
        """
        Get current balance (qty, weight) for Stock or StockItem.

        Args:
            subject: Stock or StockItem instance

        Returns:
            {'qty': int, 'wt': Decimal}
        """
        if isinstance(subject, Stock):
            return subject.current_balance()
        elif isinstance(subject, StockItem):
            return subject.current_balance()
        else:
            raise ValueError(f"Subject must be Stock or StockItem, got {type(subject)}")
