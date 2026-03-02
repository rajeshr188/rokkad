from abc import ABC, abstractmethod

from ..types import PostingRule, PostingBundle


class BasePostingRule(PostingRule, ABC):
    rule_version = "1"  # override when logic materially changes
    voucher_type: str  # must be set by subclasses

    @abstractmethod
    def build_posting(self, ctx) -> PostingBundle:
        ...

    def fingerprint_payload(self, ctx):
        """
        Default, conservative payload; override to add salient fields (totals, currency, dates).
        Must be JSON-serializable by engine.compute_fingerprint.
        """
        doc_payload = {}
        if ctx.doc and hasattr(ctx.doc, "get_economic_payload"):
            doc_payload = ctx.doc.get_economic_payload() or {}
        return {
            "voucher_type": getattr(self.voucher_type, "name", self.voucher_type),
            "rule_version": self.rule_version,
            "doc": doc_payload,
        }
