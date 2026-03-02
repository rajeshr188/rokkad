from django.db import models
from django.contrib.auth import get_user_model
import logging

user = get_user_model()
logger = logging.getLogger(__name__)

user = get_user_model()


class BusinessDoc(models.Model):
    """
    Domain Event representation.
    Eg: LoanDisbursement, LoanRepayment, Purchase, Sale...
    """

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        user, on_delete=models.SET_NULL, null=True, related_name="%(class)s_created_by"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(user, on_delete=models.SET_NULL, null=True)
    # Control auto-posting behavior
    auto_post_to_accounting = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Auto-post to accounting after successful save
        if self.auto_post_to_accounting:
            self._auto_post_to_accounting()

    def _auto_post_to_accounting(self):
        """Delegate to service layer for idempotent posting."""
        from ..services.post_doc import create_and_post_voucher_for_doc
        from ..posting.engine import DjangoPostingEngine

        try:
            voucher, je = create_and_post_voucher_for_doc(
                doc=self,
                user=self.updated_by or self.created_by,  # Use updated_by if exists
                voucher_type_input=self.get_voucher_type(),
                engine=DjangoPostingEngine(),
            )
            logger.info(
                f"Posted voucher {voucher.voucher_no} for {self.__class__.__name__} #{self.id}"
            )
        except Exception as e:
            logger.error(
                f"Auto-posting failed for {self.__class__.__name__} #{self.id}: {e}"
            )
            # Don't raise—allow doc to save even if posting fails

    def get_voucher_type(self) -> str:
        """Default voucher type mapping - override if needed"""
        return self.__class__.__name__.upper()

    def get_economic_payload(self) -> dict:
        """Override in subclasses with economic fields only"""
        return {}
