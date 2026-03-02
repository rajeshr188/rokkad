"""
Example Django settings configuration for SaaS monetization with Razorpay.

Add these settings to your django_project/settings.py or settings/base.py
"""

import os
from decimal import Decimal

# ============================================================================
# RAZORPAY PAYMENT GATEWAY CONFIGURATION
# ============================================================================

# Get from environment variables (more secure)
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

# Note: For development, you can use test keys:
# Test Key ID: rzp_test_xxxxxxxxxxxxxxxx
# Test Secret: xxxxxxxxxxxxxxxx
# Available on https://razorpay.com/app/keys


# ============================================================================
# SUBSCRIPTION & BILLING SETTINGS
# ============================================================================

# Default trial period in days
SUBSCRIPTION_DEFAULT_TRIAL_DAYS = 14

# Payment due date (days after invoice creation)
BILLING_DUE_DATE_DAYS = 7

# Auto-payment attempt days (for recurring subscriptions)
BILLING_AUTO_PAYMENT_DAYS = 30

# Service suspension days (days after due date)
BILLING_SUSPENSION_DAYS = 5

# GST/Tax rate for India (in percentage)
BILLING_TAX_RATE = Decimal("18.00")

# Country for billing
BILLING_COUNTRY = "IN"
BILLING_CURRENCY = "INR"


# ============================================================================
# SUBSCRIPTION PLAN CONFIGURATION
# ============================================================================

# Pricing tiers (in INR)
SUBSCRIPTION_PLANS = {
    "starter": {
        "name": "Starter",
        "price": Decimal("999.00"),
        "yearly_price": Decimal("9990.00"),
        "max_users": 5,
        "max_products": 100,
        "max_invoices_per_month": 500,
        "max_transactions_per_month": 500,
    },
    "professional": {
        "name": "Professional",
        "price": Decimal("3999.00"),
        "yearly_price": Decimal("39990.00"),
        "max_users": 50,
        "max_products": 2000,
        "max_invoices_per_month": 10000,
        "max_transactions_per_month": 10000,
    },
    "enterprise": {
        "name": "Enterprise",
        "price": None,  # Custom pricing
        "yearly_price": None,
        "max_users": 999999,
        "max_products": 999999,
        "max_invoices_per_month": 999999,
        "max_transactions_per_month": 999999,
    },
}

# Extra cost per additional user (INR)
BILLING_EXTRA_USER_PRICE = Decimal("99.00")

# Price for additional features
BILLING_FEATURE_PRICES = {
    "advanced_reporting": Decimal("0.00"),  # Included in Professional+
    "multi_warehouse": Decimal("0.00"),  # Included in Professional+
    "api_access": Decimal("2000.00"),  # Add-on: ₹2000/month
    "dedicated_support": Decimal("5000.00"),  # Add-on: ₹5000/month
}


# ============================================================================
# PAYMENT GATEWAY CONFIGURATION
# ============================================================================

# Razorpay payment methods to display
RAZORPAY_PAYMENT_METHODS = [
    "card",  # Credit/Debit card
    "netbanking",  # Net banking
    "upi",  # UPI
    "wallet",  # Digital wallets
    "emandate",  # E-Mandate (auto-pay)
]

# Enable auto-renewal for subscriptions
RAZORPAY_AUTO_RENEWAL = True

# Minimum amount for Razorpay payment (in INR)
RAZORPAY_MINIMUM_AMOUNT = Decimal("1.00")

# Maximum amount for Razorpay payment (in INR)
RAZORPAY_MAXIMUM_AMOUNT = Decimal("999999.00")


# ============================================================================
# EMAIL NOTIFICATION SETTINGS FOR BILLING
# ============================================================================

# Email template settings
BILLING_EMAIL_SENDER = "billing@yourdomain.com"
BILLING_EMAIL_SUPPORT = "support@yourdomain.com"

# Send invoice email after payment
SEND_INVOICE_EMAIL = True

# Send renewal reminder email (X days before renewal)
SEND_RENEWAL_REMINDER = True
RENEWAL_REMINDER_DAYS = 3

# Send payment failed email
SEND_PAYMENT_FAILED_EMAIL = True

# Send dunning emails for unpaid invoices
SEND_DUNNING_EMAILS = True


# ============================================================================
# WEBHOOK CONFIGURATION
# ============================================================================

# Razorpay webhook events to listen for
RAZORPAY_WEBHOOK_EVENTS = [
    "payment.authorized",
    "payment.captured",
    "payment.failed",
    "payment.refunded",
    "subscription.created",
    "subscription.charged",
    "subscription.paused",
    "subscription.resumed",
    "subscription.cancelled",
    "subscription.halted",
    "subscription.completed",
]

# Webhook verification retry count
WEBHOOK_RETRY_COUNT = 3


# ============================================================================
# INVOICE & DOCUMENT SETTINGS
# ============================================================================

# Invoice prefix
INVOICE_NUMBER_PREFIX = "INV"

# Day to generate invoices (1-28 for date, or 'cycle_start')
INVOICE_GENERATION_DAY = "cycle_start"

# Enable invoice PDF generation
ENABLE_PDF_INVOICES = True

# PDF invoice footer text
PDF_INVOICE_FOOTER = (
    "Thank you for using Rokkad. For support, contact support@rokkad.com\n"
    "GST Registration: XXXXXXXXXXXXXXXX"
)


# ============================================================================
# FEATURE ACCESS CONTROL
# ============================================================================

# Features that require subscription verification
PREMIUM_FEATURES = {
    "advanced_reporting": "professional",  # Requires Professional or higher
    "multi_warehouse": "professional",
    "approvals_workflow": "professional",
    "api_access": "enterprise",
    "custom_fields": "professional",
    "team_collabration": "professional",
    "bulk_import": "professional",
}


# ============================================================================
# ANALYTICS & REPORTING
# ============================================================================

# Track subscription metrics
TRACK_SUBSCRIPTION_METRICS = True

# Metrics to track
TRACKED_METRICS = [
    "active_users",
    "invoices_created",
    "transactions_processed",
    "products_added",
    "report_generated",
    "api_calls",
]

# Days to retain metrics data (before cleanup)
METRICS_RETENTION_DAYS = 365


# ============================================================================
# SECURITY SETTINGS
# ============================================================================

# Enable PCI DSS compliance check
REQUIRE_PCI_COMPLIANCE = True

# Encrypt sensitive payment data
ENCRYPT_PAYMENT_DATA = True

# Allow only HTTPS for payment pages
PAYMENT_REQUIRE_HTTPS = True

# Payment session timeout (in minutes)
PAYMENT_SESSION_TIMEOUT = 30


# ============================================================================
# DISCOUNT & PROMOTION SETTINGS
# ============================================================================

# Enable coupon codes
ENABLE_COUPONS = True

# Enable referral program
ENABLE_REFERRAL_PROGRAM = True
REFERRAL_COMMISSION_PERCENT = 20  # 20% commission per referral

# Enable promotional discounts
ENABLE_PROMOTIONS = True

# Launch promotion discount (for first month)
LAUNCH_PROMOTION_DISCOUNT = 50  # ₹50 off


# ============================================================================
# DUNNING POLICY (Recovery for failed payments)
# ============================================================================

DUNNING_CONFIG = {
    "attempts": 3,  # Number of retry attempts
    "days_between_attempts": 5,  # Days between each attempt
    "days_before_suspension": 30,  # Days before service suspension
    "days_before_cancellation": 60,  # Days before subscription cancellation
}


# ============================================================================
# INSTALLED APPS (Add this to your INSTALLED_APPS)
# ============================================================================

# INSTALLED_APPS = [
#     ...
#     'apps.subscriptions',
#     ...
# ]
