from decimal import Decimal

from dynamic_preferences.preferences import Section
from dynamic_preferences.registries import global_preferences_registry
from dynamic_preferences.types import (
    BooleanPreference,
    ChoicePreference,
    DecimalPreference,
)

from apps.orgs.registries import company_preference_registry

loan_section = Section("Loan")
interest_rate_section = Section("Interest_Rate")


# @company_preference_registry.register
# class LoanTemplate(ChoicePreference):
#     section = "Loan"
#     name = "LoanPDFTemplate"
#     default = "d"
#     choices = [
#         ("d", "Default"),
#         ("c", "Custom_JSK"),
#         ("j", "Custom_JCL"),
#     ]
#     required = True


class BaseLoanInterestDeduction(BooleanPreference):
    section = loan_section
    name = "Interest_Deduction"
    default = False
    required = False


@global_preferences_registry.register
class GlobalLoanInterestDeduction(BaseLoanInterestDeduction):
    pass


@company_preference_registry.register
class CompanyLoanInterestDeduction(BaseLoanInterestDeduction):
    pass


class BaseGoldInterestRate(DecimalPreference):
    section = interest_rate_section
    name = "gold"
    default = Decimal("2.00")
    required = True


@global_preferences_registry.register
class GlobalGoldInterestRate(BaseGoldInterestRate):
    pass


@company_preference_registry.register
class CompanyGoldInterestRate(BaseGoldInterestRate):
    pass


class BaseSilverInterestRate(DecimalPreference):
    section = interest_rate_section
    name = "silver"
    default = Decimal("4.00")
    required = True


@global_preferences_registry.register
class GlobalSilverInterestRate(BaseSilverInterestRate):
    pass


@company_preference_registry.register
class CompanySilverInterestRate(BaseSilverInterestRate):
    pass


class BaseOtherInterestRate(DecimalPreference):
    section = interest_rate_section
    name = "other"
    default = Decimal("8.00")
    required = True


@global_preferences_registry.register
class GlobalOtherInterestRate(BaseOtherInterestRate):
    pass


@company_preference_registry.register
class CompanyOtherInterestRate(BaseOtherInterestRate):
    pass


class BaseLoanDefaultDate(ChoicePreference):
    section = loan_section
    name = "Default_Date"
    default = "N"
    choices = [
        ("N", "Now"),
        ("L", "Last Object Created"),
    ]


@global_preferences_registry.register
class GlobalLoanDefaultDate(BaseLoanDefaultDate):
    pass


@company_preference_registry.register
class CompanyLoanDefaultDate(BaseLoanDefaultDate):
    pass


class BaseLoanHaircut(DecimalPreference):
    section = loan_section
    name = "Haircut"
    default = Decimal("75.00")
    required = True


@global_preferences_registry.register
class GlobalLoanHaircut(BaseLoanHaircut):
    pass


@company_preference_registry.register
class CompanyLoanHaircut(BaseLoanHaircut):
    pass
