from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import TestCase

from apps.tenant_apps.accounting.domain import (
    AccountingBook,
    AccountingPeriod,
    CurrencyPolicy,
    DomainValidationError,
    LedgerSide,
    LedgerTransaction,
    MonetaryAmount,
    PeriodStatus,
    PostingPurpose,
    PostingRuleIdentity,
    SourceEventIdentity,
    VoucherIntent,
    VoucherState,
    correct_posting,
    post_voucher,
    reverse_posting,
)


BOOK = AccountingBook(book_key="PRIMARY-INR", base_currency="INR")
POLICY = CurrencyPolicy(base_currency="INR", decimal_places=2)
OPEN_PERIOD = AccountingPeriod(
    period_key="FY26-AUG",
    book_key=BOOK.book_key,
    start_date=date(2026, 8, 1),
    end_date=date(2026, 8, 31),
    status=PeriodStatus.OPEN,
)
AUTHORIZED_AT = datetime(2026, 8, 7, 10, 30, tzinfo=timezone.utc)


def inr(value: str) -> MonetaryAmount:
    return MonetaryAmount(
        amount=Decimal(value),
        currency="INR",
        base_amount=Decimal(value),
        base_currency="INR",
        exchange_rate=Decimal("1"),
        rate_source="BOOK_BASE_CURRENCY",
    )


def sale_transaction(value: str = "1000") -> LedgerTransaction:
    return LedgerTransaction(
        transaction_key="SALE-T1",
        debit_ledger_key="CASH",
        credit_ledger_key="SALES_REVENUE",
        money=inr(value),
    )


def draft_voucher(
    *,
    book_key: str = BOOK.book_key,
    idempotency_key: str = "sales:invoice:100:v1",
    source_version: str = "1",
    rule_version: str = "1",
    amount: str = "1000",
    purpose: PostingPurpose = PostingPurpose.ORDINARY,
) -> VoucherIntent:
    return VoucherIntent(
        voucher_key=f"V-{book_key}-100",
        book_key=book_key,
        idempotency_key=idempotency_key,
        effective_date=date(2026, 8, 7),
        source=SourceEventIdentity(
            source_system="SALES",
            source_type="INVOICE",
            source_id="100",
            source_version=source_version,
        ),
        rule=PostingRuleIdentity(
            rule_key="CASH_SALE",
            rule_version=rule_version,
        ),
        transactions=(sale_transaction(amount),),
        purpose=purpose,
    )


def authorize(voucher: VoucherIntent) -> VoucherIntent:
    return voucher.authorize(actor_key="accountant:1", authorized_at=AUTHORIZED_AT)


class VoucherAuthorizationTests(TestCase):
    def test_draft_is_immutable_and_authorization_returns_a_new_voucher(self):
        draft = draft_voucher()
        authorized = authorize(draft)
        self.assertEqual(draft.state, VoucherState.DRAFT)
        self.assertIsNone(draft.authorized_by)
        self.assertEqual(authorized.state, VoucherState.AUTHORIZED)
        self.assertEqual(authorized.authorized_by, "accountant:1")
        self.assertEqual(authorized.authorized_at, AUTHORIZED_AT)

    def test_only_authorized_voucher_can_post(self):
        with self.assertRaises(DomainValidationError):
            post_voucher(
                draft_voucher(),
                book=BOOK,
                period=OPEN_PERIOD,
                currency_policy=POLICY,
            )

    def test_source_and_rule_versions_are_preserved_on_posting_record(self):
        result = post_voucher(
            authorize(draft_voucher(source_version="7", rule_version="3")),
            book=BOOK,
            period=OPEN_PERIOD,
            currency_policy=POLICY,
        )
        self.assertEqual(result.record.source.source_version, "7")
        self.assertEqual(result.record.rule.rule_version, "3")
        self.assertEqual(result.record.batch.transactions, (sale_transaction(),))


class IdempotencyTests(TestCase):
    def test_exact_book_scoped_replay_returns_existing_posting(self):
        voucher = authorize(draft_voucher())
        first = post_voucher(
            voucher, book=BOOK, period=OPEN_PERIOD, currency_policy=POLICY
        )
        replay = post_voucher(
            voucher,
            book=BOOK,
            period=OPEN_PERIOD,
            currency_policy=POLICY,
            prior_postings=(first.record,),
        )
        self.assertFalse(first.replayed)
        self.assertTrue(replay.replayed)
        self.assertIs(replay.record, first.record)

    def test_same_key_with_changed_amount_source_or_rule_fails(self):
        original = post_voucher(
            authorize(draft_voucher()),
            book=BOOK,
            period=OPEN_PERIOD,
            currency_policy=POLICY,
        ).record
        variants = (
            draft_voucher(amount="1001"),
            draft_voucher(source_version="2"),
            draft_voucher(rule_version="2"),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(DomainValidationError):
                    post_voucher(
                        authorize(variant),
                        book=BOOK,
                        period=OPEN_PERIOD,
                        currency_policy=POLICY,
                        prior_postings=(original,),
                    )

    def test_same_idempotency_key_is_independent_in_another_book(self):
        first = post_voucher(
            authorize(draft_voucher()),
            book=BOOK,
            period=OPEN_PERIOD,
            currency_policy=POLICY,
        ).record
        second_book = AccountingBook(book_key="SECONDARY-INR", base_currency="INR")
        second_period = AccountingPeriod(
            period_key="SECONDARY-AUG",
            book_key=second_book.book_key,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status=PeriodStatus.OPEN,
        )
        second = post_voucher(
            authorize(draft_voucher(book_key=second_book.book_key)),
            book=second_book,
            period=second_period,
            currency_policy=POLICY,
            prior_postings=(first,),
        )
        self.assertFalse(second.replayed)
        self.assertNotEqual(second.record.book_key, first.book_key)


class PeriodAndCurrencyTests(TestCase):
    def test_period_date_and_book_must_match(self):
        wrong_period = AccountingPeriod(
            period_key="FY26-JUL",
            book_key=BOOK.book_key,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            status=PeriodStatus.OPEN,
        )
        with self.assertRaises(DomainValidationError):
            post_voucher(
                authorize(draft_voucher()),
                book=BOOK,
                period=wrong_period,
                currency_policy=POLICY,
            )

    def test_adjustment_only_period_rejects_ordinary_and_accepts_adjustment(self):
        adjustment_period = AccountingPeriod(
            period_key="FY26-AUG-ADJ",
            book_key=BOOK.book_key,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status=PeriodStatus.ADJUSTMENT_ONLY,
        )
        with self.assertRaises(DomainValidationError):
            post_voucher(
                authorize(draft_voucher()),
                book=BOOK,
                period=adjustment_period,
                currency_policy=POLICY,
            )
        adjustment = post_voucher(
            authorize(
                draft_voucher(
                    idempotency_key="sales:adjustment:100:v1",
                    purpose=PostingPurpose.ADJUSTMENT,
                )
            ),
            book=BOOK,
            period=adjustment_period,
            currency_policy=POLICY,
        )
        self.assertFalse(adjustment.replayed)

    def test_closed_and_locked_periods_fail_closed(self):
        for status in (PeriodStatus.CLOSED, PeriodStatus.LOCKED):
            period = AccountingPeriod(
                period_key=f"FY26-AUG-{status.value}",
                book_key=BOOK.book_key,
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 31),
                status=status,
            )
            with self.subTest(status=status):
                with self.assertRaises(DomainValidationError):
                    post_voucher(
                        authorize(draft_voucher()),
                        book=BOOK,
                        period=period,
                        currency_policy=POLICY,
                    )

    def test_foreign_currency_base_amount_must_match_rate_and_policy(self):
        correct_money = MonetaryAmount(
            amount=Decimal("10"),
            currency="USD",
            base_amount=Decimal("830.00"),
            base_currency="INR",
            exchange_rate=Decimal("83"),
            rate_source="RBI:2026-08-07",
        )
        transaction = LedgerTransaction(
            transaction_key="FX-SALE-T1",
            debit_ledger_key="BANK",
            credit_ledger_key="SALES_REVENUE",
            money=correct_money,
        )
        voucher = authorize(
            VoucherIntent(
                voucher_key="FX-SALE-1",
                book_key=BOOK.book_key,
                idempotency_key="fx-sale:1",
                effective_date=date(2026, 8, 7),
                source=SourceEventIdentity("SALES", "INVOICE", "FX-1", "1"),
                rule=PostingRuleIdentity("FX_CASH_SALE", "1"),
                transactions=(transaction,),
            )
        )
        self.assertFalse(
            post_voucher(
                voucher,
                book=BOOK,
                period=OPEN_PERIOD,
                currency_policy=POLICY,
            ).replayed
        )
        bad_money = MonetaryAmount(
            amount=Decimal("10"),
            currency="USD",
            base_amount=Decimal("829.99"),
            base_currency="INR",
            exchange_rate=Decimal("83"),
            rate_source="RBI:2026-08-07",
        )
        bad_voucher = VoucherIntent(
            voucher_key="FX-SALE-BAD",
            book_key=BOOK.book_key,
            idempotency_key="fx-sale:bad",
            effective_date=date(2026, 8, 7),
            source=SourceEventIdentity("SALES", "INVOICE", "FX-BAD", "1"),
            rule=PostingRuleIdentity("FX_CASH_SALE", "1"),
            transactions=(
                LedgerTransaction(
                    transaction_key="FX-SALE-BAD-T1",
                    debit_ledger_key="BANK",
                    credit_ledger_key="SALES_REVENUE",
                    money=bad_money,
                ),
            ),
        )
        with self.assertRaises(DomainValidationError):
            post_voucher(
                authorize(bad_voucher),
                book=BOOK,
                period=OPEN_PERIOD,
                currency_policy=POLICY,
            )


class ReversalAndCorrectionTests(TestCase):
    def original_record(self):
        return post_voucher(
            authorize(draft_voucher()),
            book=BOOK,
            period=OPEN_PERIOD,
            currency_policy=POLICY,
        ).record

    def test_reversal_is_new_evidence_and_does_not_mutate_original(self):
        original = self.original_record()
        original_batch = original.batch
        reversal = reverse_posting(
            original,
            reversal_batch_key="REV:V-PRIMARY-INR-100",
            reversal_idempotency_key="sales:invoice:100:reversal",
            reversal_date=date(2026, 8, 8),
            actor_key="accounting-admin:1",
            reason="Incorrect amount",
            book=BOOK,
            period=OPEN_PERIOD,
        )
        self.assertIs(original.batch, original_batch)
        self.assertEqual(reversal.reversal_batch.reversal_of_batch_key, original.batch.batch_key)
        self.assertEqual(
            reversal.reversal_batch.transactions[0].debit_ledger_key,
            "SALES_REVENUE",
        )
        self.assertEqual(reversal.reason, "Incorrect amount")

    def test_correction_is_original_plus_reversal_plus_new_posting(self):
        original = self.original_record()
        corrected = authorize(
            draft_voucher(
                idempotency_key="sales:invoice:100:correction:1",
                source_version="2",
                amount="900",
            )
        )
        result = correct_posting(
            original,
            corrected,
            reversal_batch_key="REV:V-PRIMARY-INR-100",
            reversal_idempotency_key="sales:invoice:100:reversal",
            correction_date=date(2026, 8, 8),
            actor_key="accounting-admin:1",
            reason="Correct sale amount",
            book=BOOK,
            period=OPEN_PERIOD,
            currency_policy=POLICY,
        )
        self.assertIs(result.original, original)
        self.assertEqual(result.reversal.reversal_batch.reversal_of_batch_key, original.batch.batch_key)
        self.assertEqual(result.replacement.source.source_version, "2")
        self.assertEqual(result.replacement.batch.transactions[0].money.amount, Decimal("900"))
        self.assertNotEqual(result.replacement.fingerprint, original.fingerprint)

    def test_reversal_requires_actor_reason_and_open_adjustment_period(self):
        original = self.original_record()
        with self.assertRaises(DomainValidationError):
            reverse_posting(
                original,
                reversal_batch_key="REV:BAD",
                reversal_idempotency_key="rev:bad",
                reversal_date=date(2026, 8, 8),
                actor_key="accounting-admin:1",
                reason="",
                book=BOOK,
                period=OPEN_PERIOD,
            )
