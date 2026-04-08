from decimal import Decimal

from dynamic_preferences.registries import global_preferences_registry
from dynamic_preferences.settings import preferences_settings

from .models import CompanyPreferenceModel


class CompanyPreferences:
    DEFAULTS = {
        "Loan__Default_Date": "N",
        "Loan__Interest_Deduction": False,
        "Loan__Haircut": Decimal("75.00"),
        "Interest_Rate__gold": Decimal("2.00"),
        "Interest_Rate__silver": Decimal("4.00"),
        "Interest_Rate__other": Decimal("8.00"),
        "Loan__Accrual_Timing": "EOM",
        "Loan__Auto_Post_Accruals": True,
        "Loan__Catchup_On_Receipt": True,
        "Loan__Catchup_On_Release": True,
        "Loan__Catchup_On_Renewal": True,
        "Loan__Allow_Backfill_Posting": False,
    }

    def __init__(self, company=None):
        self.company = company
        self._global_prefs = global_preferences_registry.manager()
        self._overrides = set()
        if company is not None:
            try:
                self._overrides = set(
                    CompanyPreferenceModel.objects.filter(instance=company).values_list(
                        "section", "name"
                    )
                )
            except Exception:
                self._overrides = set()

    def _get(self, key):
        section, name = key.split(preferences_settings.SECTION_KEY_SEPARATOR, 1)
        try:
            if self.company is not None and (section, name) in self._overrides:
                return self.company.preferences[key]
            return self._global_prefs[key]
        except Exception:
            return self.DEFAULTS.get(key)

    @property
    def loan_default_date(self):
        return self._get("Loan__Default_Date")

    @property
    def loan_interest_deduction(self):
        return self._get("Loan__Interest_Deduction")

    @property
    def loan_haircut(self):
        return self._get("Loan__Haircut")

    @property
    def interest_rate_gold(self):
        return self._get("Interest_Rate__gold")

    @property
    def interest_rate_silver(self):
        return self._get("Interest_Rate__silver")

    @property
    def interest_rate_other(self):
        return self._get("Interest_Rate__other")

    @property
    def loan_accrual_timing(self):
        return self._get("Loan__Accrual_Timing")

    @property
    def loan_auto_post_accruals(self):
        return self._get("Loan__Auto_Post_Accruals")

    @property
    def loan_catchup_on_receipt(self):
        return self._get("Loan__Catchup_On_Receipt")

    @property
    def loan_catchup_on_release(self):
        return self._get("Loan__Catchup_On_Release")

    @property
    def loan_catchup_on_renewal(self):
        return self._get("Loan__Catchup_On_Renewal")

    @property
    def loan_allow_backfill_posting(self):
        return self._get("Loan__Allow_Backfill_Posting")
