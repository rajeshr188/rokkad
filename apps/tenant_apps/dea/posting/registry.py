# accounting/posting/registry.py
from .types import PostingRule, RuleNotFoundError


class PostingRuleRegistry:
    def __init__(self):
        self._rules: dict[str, PostingRule] = {}

    def register(self, voucher_type: str, rule_cls_or_instance: PostingRule):
        """
        rule_cls must be subclass of PostingRule
        """
        rule = (
            rule_cls_or_instance()
            if isinstance(rule_cls_or_instance, type)
            else rule_cls_or_instance
        )
        if not hasattr(rule, "build_posting"):
            raise TypeError(
                f"Rule for '{voucher_type}' must implement build_posting(ctx)"
            )
        if not hasattr(rule, "rule_version"):
            rule.rule_version = "1"
        if voucher_type in self._rules:
            raise ValueError(
                f"Rule already registered for voucher_type '{voucher_type}'"
            )
        self._rules[voucher_type] = rule
        # self._rules[voucher_type] = rule_cls()

    def get(self, voucher_type: str) -> PostingRule:
        try:
            return self._rules[voucher_type]
        except KeyError:
            raise RuleNotFoundError(
                f"No posting rule found for voucher_type '{voucher_type}'"
            )


def register_rule(voucher_type: str):
    def decorator(cls):
        registry.register(voucher_type, cls)
        return cls

    return decorator


# single global registry instance used by engine
registry = PostingRuleRegistry()
