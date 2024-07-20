import datetime
from decimal import Decimal

from dynamic_preferences.preferences import Section
from dynamic_preferences.registries import global_preferences_registry
from dynamic_preferences.types import (BooleanPreference, ChoicePreference,
                                       DatePreference, DecimalPreference)

from apps.orgs.registries import company_preference_registry

general = Section("general")


@company_preference_registry.register
class LoanTemplate(ChoicePreference):
    section = "Loan"
    name = "LoanPDFTemplate"
    default = "d"
    choices = [
        ("d", "Default"),
        ("c", "Custom_JSK"),
    ]
    required = True


@company_preference_registry.register
class LoanInterestDeduction(BooleanPreference):
    section = "Loan"
    name = "Interest_Deduction"
    default = False
    required = True


# @global_preferences_registry.register
@company_preference_registry.register
class GoldInterestRate(DecimalPreference):
    section = "Interest_Rate"
    name = "gold"
    default = Decimal("2.00")
    required = True


# @global_preferences_registry.register
@company_preference_registry.register
class SilverInterestRate(DecimalPreference):
    section = "Interest_Rate"
    name = "silver"
    default = Decimal("4.00")
    required = True


# @global_preferences_registry.register
@company_preference_registry.register
class OtherInterestRate(DecimalPreference):
    section = "Interest_Rate"
    name = "other"
    default = Decimal("8.00")
    required = True


# @global_preferences_registry.register
@company_preference_registry.register
class Loandate(ChoicePreference):
    choices = (
        ("N", "Now"),
        ("L", "Last Object Created"),
    )
    default = "C"
    section = "Loan"
    name = "Default_Date"
    default = "N"


# @global_preferences_registry.register
@company_preference_registry.register
class LoanHaircut(DecimalPreference):
    section = "Loan"
    name = "Haircut"
    default = Decimal("75.00")
    required = True
