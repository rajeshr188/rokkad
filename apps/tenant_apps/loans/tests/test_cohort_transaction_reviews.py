"""Bounded source cohorts reuse immutable per-loan capture confirmations."""
from copy import deepcopy
from datetime import date
from uuid import uuid4
from unittest.mock import patch
from django.db import connection,transaction,DatabaseError

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.batch_transaction_reviews import (
    preview_cohort_transaction_review, confirm_cohort_transaction_review,
)
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from . import test_opening_import as fixtures


class CohortReviewTests(fixtures.OpeningImportFixture):
    day=date(2021,2,2)

    def opening(self, number):
        review=deepcopy(self.review)
        review['source'].update(loan_id=f'girvi_loan:{number}',number=f'A{number:05d}',
            item_ids=[f'girvi_loanitem:{number}'])
        review['collateral'][0]['id']=f'girvi_loanitem:{number}'
        return self.write(review=review)

    def facts(self):
        return dict(workspace=self.a,actor=self.actor,series=self.series,
            source_namespace=self.review['source']['namespace'],after_loan_id=0,
            through_date=self.day,confirmed_complete=True,source_reference='Accepted cutover and all later book activity checked',
            future_capture='ROKKAD_ONLY',request_key=uuid4().hex)

    def test_checkpoint_forward_confirmation_retry_and_financial_preservation(self):
        with self.scoped(),patch('django.utils.timezone.localdate',return_value=self.day):
            first,second=self.opening(1),self.opening(2)
            financial=list(m.PawnLoanEvent.objects.values_list('pk','payload_fingerprint'))
            facts=self.facts()
            review,token=preview_cohort_transaction_review(**facts)
            self.assertEqual((review['selected'],review['eligible'],len(review['exceptions'])),(2,2,0))
            self.assertEqual({row['history_from'] for row in review['rows']},{'2021-01-20'})
            self.assertFalse(m.LoanTransactionReview.objects.exists())
            with self.assertRaises(ValueError):
                confirm_cohort_transaction_review(**facts,review_token=token,acknowledged='yes')
            result,_=confirm_cohort_transaction_review(**facts,review_token=token,acknowledged=True)
            self.assertTrue(all(created for _,created in result))
            retry,_=confirm_cohort_transaction_review(**facts,review_token=token,acknowledged=True)
            self.assertTrue(all(not created for _,created in retry))
            self.assertEqual(list(m.PawnLoanEvent.objects.values_list('pk','payload_fingerprint')),financial)
            for origin in (first,second):
                check=origin.loan.transaction_reviews.get()
                self.assertIn(str(origin.source_namespace),check.source_reference)
                self.assertEqual(transaction_completeness(origin.loan,self.day).status,'ROKKAD_ONLY')

    def test_exceptions_are_explicit_and_are_never_confirmed(self):
        with self.scoped(),patch('django.utils.timezone.localdate',return_value=self.day):
            first,second=self.opening(1),self.opening(2)
            def inspect(loan_id,**data):
                if loan_id==second.loan_id:
                    raise ValueError('Source position needs reconciliation')
                return preview_transaction_review(loan_id,**data)
            facts=self.facts()
            with patch('apps.tenant_apps.loans.services.batch_transaction_reviews.preview_transaction_review',side_effect=inspect):
                review,token=preview_cohort_transaction_review(**facts)
            self.assertEqual(review['eligible'],1)
            self.assertEqual(review['exceptions'][0]['loan'],second.loan_id)
            confirm_cohort_transaction_review(**facts,review_token=token,acknowledged=True)
            self.assertTrue(first.loan.transaction_reviews.exists())
            self.assertFalse(second.loan.transaction_reviews.exists())

    def test_scope_choice_and_changed_activity_cannot_reuse_the_signed_review(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with self.scoped(),patch('django.utils.timezone.localdate',return_value=self.day):
            origin=self.opening(1)
            facts=self.facts()
            _,token=preview_cohort_transaction_review(**facts)
            with self.assertRaises(ValueError):
                confirm_cohort_transaction_review(**dict(facts,future_capture='PAPER_MIXED'),
                    review_token=token,acknowledged=True)
            record_pawn_loan_repayment(origin.loan_id,amount='10',request_key='after-preview',actor=self.actor)
            with self.assertRaises(ValueError):
                confirm_cohort_transaction_review(**facts,review_token=token,acknowledged=True)
            self.assertFalse(m.LoanTransactionReview.objects.exists())
        with self.scoped(self.b),self.assertRaises(ValueError):
            preview_cohort_transaction_review(**dict(facts,workspace=self.b))

    def test_source_selection_is_bounded_and_cursor_continues_the_cohort(self):
        with self.scoped(),patch('django.utils.timezone.localdate',return_value=self.day):
            for number in range(1,52):
                self.opening(number)
            facts=self.facts()
            review,_=preview_cohort_transaction_review(**facts)
            self.assertEqual((review['selected'],review['eligible'],review['more']),(50,50,True))
            tail,_=preview_cohort_transaction_review(**dict(facts,after_loan_id=review['next_cursor']))
            self.assertEqual((tail['selected'],tail['eligible'],tail['more']),(1,1,False))
            self.assertFalse(m.LoanTransactionReview.objects.exists())

    def test_restricted_database_review_cannot_precede_the_accepted_checkpoint(self):
        with self.scoped():
            origin=self.opening(1)
            with connection.cursor() as cursor:
                cursor.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
                self.assertEqual(cursor.fetchone(),(False,False))
            with self.assertRaises(DatabaseError),transaction.atomic():
                m.LoanTransactionReview.objects.create(workspace=self.a,loan=origin.loan,
                    through_date=date(2021,1,10),confirmed_complete=True,source_reference='Invalid pre-cutover review',
                    source_fingerprint='a'*64,request_key='before-opening',reviewed_by=self.actor)
