# accounting/posting/commands.py

from .engine import BasePostingEngine
from .context import PostingContext


class PostVoucherCommand:
    """
    Entry point for outside world.  (views / signals / services)
    """

    def __init__(self, engine: BasePostingEngine):
        self.engine = engine

    def execute(self, voucher, user):
        ctx = PostingContext(
            voucher=voucher,
            doc=getattr(voucher, "business_doc", None),
            user_id=getattr(user, "id", None),
        )
        return self.engine.post(ctx)
