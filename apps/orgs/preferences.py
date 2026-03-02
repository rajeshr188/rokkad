from dynamic_preferences.registries import global_preferences_registry
from dynamic_preferences.settings import preferences_settings

from .models import CompanyPreferenceModel


class CompanyPreferences:
    def __init__(self, company):
        self.company = company
        self._global_prefs = global_preferences_registry.manager()
        self._overrides = set(
            CompanyPreferenceModel.objects.filter(instance=company).values_list(
                "section", "name"
            )
        )

    def _get(self, key):
        section, name = key.split(preferences_settings.SECTION_KEY_SEPARATOR, 1)
        if (section, name) in self._overrides:
            return self.company.preferences[key]
        return self._global_prefs[key]

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
