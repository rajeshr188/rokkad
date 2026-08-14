"""Pure loan-domain vocabulary and policies."""

from .auctions import PawnLoanAuctionState
from .renewals import PawnLoanRenewalMode
from .collateral_economics import (
    CollateralEconomicsError,
    CollateralTrancheInput,
    CollateralTrancheResult,
    DisbursalFeeInput,
    DisbursalFeeResult,
    FeeCalculationType,
    PawnDisbursalEconomics,
    calculate_pawn_disbursal_economics,
)
from .future_funding import FundingLoanState
from .notices import (
    PawnLoanNoticeChannel,
    PawnLoanNoticeKind,
    PawnLoanNoticeStatus,
    SUPPORTED_PAWN_LOAN_NOTICE_KINDS,
    STAFF_CREATABLE_PAWN_LOAN_NOTICE_KINDS,
)
from .policies import (
    AccountingRecognition,
    DisbursalPolicySnapshot,
    InterestMethod,
    LicensePolicyOverrides,
    PartialMonthMethod,
    ResolvedLoanPolicy,
    RoundingMethod,
    ValuationMethod,
    WorkspacePolicyDefaults,
    resolve_policy,
)
from .products import (
    LoanAmortisationMethod,
    LoanExtraPaymentRule,
    LoanPaymentFrequency,
    LoanProductVersionStatus,
    LoanRepaymentStructure,
)
from .schedules import (
    ObligationComponent,
    RepaymentSchedule,
    RepaymentScheduleContract,
    RepaymentScheduleInput,
    ScheduleRateTranche,
    ScheduledRepayment,
)
from .vocabulary import (
    ALLOWED_PAWN_LOAN_TRANSITIONS,
    STORED_PAWN_LOAN_STATES,
    CollateralCustodyState,
    CollateralMetal,
    LoanDocumentKind,
    LoanOutboxStatus,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
    can_transition,
)

__all__ = [
    "ALLOWED_PAWN_LOAN_TRANSITIONS",
    "STORED_PAWN_LOAN_STATES",
    "CollateralCustodyState",
    "CollateralMetal",
    "AccountingRecognition",
    "DisbursalPolicySnapshot",
    "FundingLoanState",
    "InterestMethod",
    "LicensePolicyOverrides",
    "LoanDocumentKind",
    "LoanOutboxStatus",
    "LoanAmortisationMethod",
    "LoanExtraPaymentRule",
    "LoanPaymentFrequency",
    "LoanProductVersionStatus",
    "LoanRepaymentStructure",
    "ObligationComponent",
    "RepaymentSchedule",
    "RepaymentScheduleContract",
    "RepaymentScheduleInput",
    "ScheduleRateTranche",
    "ScheduledRepayment",
    "PartialMonthMethod",
    "PawnLoanNoticeChannel",
    "PawnLoanAuctionState",
    "PawnLoanRenewalMode",
    "CollateralEconomicsError",
    "CollateralTrancheInput",
    "CollateralTrancheResult",
    "DisbursalFeeInput",
    "DisbursalFeeResult",
    "FeeCalculationType",
    "PawnDisbursalEconomics",
    "calculate_pawn_disbursal_economics",
    "PawnLoanNoticeKind",
    "PawnLoanNoticeStatus",
    "PawnLoanEventKind",
    "PawnLoanState",
    "ResolvedLoanPolicy",
    "RoundingMethod",
    "TransactionKind",
    "ValuationMethod",
    "WorkspacePolicyDefaults",
    "SUPPORTED_PAWN_LOAN_NOTICE_KINDS",
    "STAFF_CREATABLE_PAWN_LOAN_NOTICE_KINDS",
    "can_transition",
    "resolve_policy",
]
from .delinquency import DelinquencyResult, UnpaidObligation, calculate_delinquency
from .ltv import LtvAssessment, calculate_ltv
from .risk import PawnLoanRiskAssessment, RiskPolicy, assess_pawn_loan_risk
from .risk_transitions import RiskTransition, detect_risk_transitions
