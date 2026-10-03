"""Immutable Form E book setup, source reviews and preserved print batches."""
from django.core.exceptions import ValidationError
from django.db import models
from django_cleanup import cleanup

from .statutory import StatutoryImmutableModel, statutory_upload


class PledgeBook(StatutoryImmutableModel):
    series = models.OneToOneField('loans.LoanSeries', on_delete=models.PROTECT, related_name='pledge_book')
    title = models.CharField(max_length=100)
    layout = models.CharField(max_length=20, choices=[('facing_a4', 'Facing A4'), ('landscape_a4', 'Landscape A4')])
    starts_on = models.DateField()
    first_page = models.PositiveIntegerField(default=1)
    opening_note = models.TextField()

    def clean(self):
        if self.series_id and self.series.workspace_id != self.workspace_id:
            raise ValidationError('Book and series must belong to the same Workspace.')

    @property
    def reference(self):
        return f'E-{self.pk}'


class PledgeBookReview(StatutoryImmutableModel):
    loan = models.ForeignKey('loans.PawnLoan', on_delete=models.PROTECT, related_name='pledge_reviews')
    basis_sha256 = models.CharField(max_length=64)
    supplements = models.JSONField(default=dict, blank=True)
    source_reference = models.CharField(max_length=300)
    notes = models.TextField()
    request_key = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('loan', 'request_key'), name='loans_pledge_review_request_uniq')]

    def clean(self):
        if self.loan_id and self.loan.workspace_id != self.workspace_id:
            raise ValidationError('Review and loan must belong to the same Workspace.')


@cleanup.ignore
class PledgeBookBatch(StatutoryImmutableModel):
    book = models.ForeignKey(PledgeBook, on_delete=models.PROTECT, related_name='batches')
    first_page = models.PositiveIntegerField()
    last_page = models.PositiveIntegerField()
    mode = models.CharField(max_length=10, choices=[('full', 'Full pages'), ('partial', 'Include partial page')])
    cutoff = models.DateField()
    snapshot = models.JSONField()
    snapshot_sha256 = models.CharField(max_length=64)
    review_sha256 = models.CharField(max_length=64)
    artifact = models.FileField(upload_to=statutory_upload)
    artifact_sha256 = models.CharField(max_length=64)
    template_version = models.CharField(max_length=60)
    request_key = models.CharField(max_length=64)

    class Meta:
        ordering = ('first_page',)
        constraints = [models.UniqueConstraint(fields=('book', 'request_key'), name='loans_pledge_batch_request_uniq'),
                       models.UniqueConstraint(fields=('book', 'first_page'), name='loans_pledge_batch_page_uniq'),
                       models.CheckConstraint(condition=models.Q(last_page__gte=models.F('first_page')), name='loans_pledge_batch_page_order')]

    def clean(self):
        if self.book_id and self.book.workspace_id != self.workspace_id:
            raise ValidationError('Batch and book must belong to the same Workspace.')


class PledgeBookEntry(StatutoryImmutableModel):
    batch = models.ForeignKey(PledgeBookBatch, on_delete=models.PROTECT, related_name='entries')
    loan = models.OneToOneField('loans.PawnLoan', on_delete=models.PROTECT, related_name='pledge_book_entry')
    first_page = models.PositiveIntegerField()
    last_page = models.PositiveIntegerField()

    def clean(self):
        if self.batch_id and self.loan_id:
            if self.batch.workspace_id != self.workspace_id or self.loan.workspace_id != self.workspace_id or self.batch.book.series_id != self.loan.series_id:
                raise ValidationError('Entry, loan and book must have matching Workspace and series.')
