from django.apps import AppConfig


class DeaConfig(AppConfig):
    name = "apps.tenant_apps.dea"
    default_auto_field = "django.db.models.BigAutoField"

    # def ready(self):
    #     from apps.tenant_apps.dea import signals
    #     from .posting.registry import registry
    #     from .posting.rules.loan_disbursement import LoanDisbursementRule
    #     from .posting.rules.loan_repayment import LoanRepaymentRule
    #     registry.register("LOAN_DISBURSE", LoanDisbursementRule)
    #     registry.register("LOAN_REPAY", LoanRepaymentRule)

    def ready(self):
        from .posting import rules as rules_pkg
        import pkgutil, importlib

        # import every module in posting.rules so modules can register themselves
        for _, name, _ in pkgutil.iter_modules(rules_pkg.__path__):
            importlib.import_module(f"{rules_pkg.__name__}.{name}")
