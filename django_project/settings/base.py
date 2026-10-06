import os
from pathlib import Path

import environ
from django.contrib import messages

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),
]
# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# False if not in os.environ because of casting above
DEBUG = env("DEBUG")

# Raises Django's ImproperlyConfigured
# exception if SECRET_KEY not in os.environ
# https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-SECRET_KEY
SECRET_KEY = env("SECRET_KEY")

# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")


# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
SHARED_APPS = [
    "apps.orgs",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.postgres",
    "django.contrib.humanize",
    # Third-party
    "django_select2",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",  # new
    "allauth.socialaccount.providers.google",  # new
    "crispy_forms",
    "crispy_bootstrap5",
    "debug_toolbar",
    "mptt",
    "phonenumber_field",
    "django_tables2",
    "django_filters",
    "djmoney",
    "widget_tweaks",
    "django_htmx",
    "import_export",
    "colorfield",
    # Local
    "accounts",
    "apps.configuration",
    "apps.platform_mail.apps.PlatformMailConfig",
    "apps.tenancy.apps.TenancyConfig",
    "apps.onboarding",  # User onboarding flow
    "apps.subscriptions",
    "pages",
    "invitations",
    "apps.tenant_apps.party",
    "apps.tenant_apps.data_portability.apps.DataPortabilityConfig",
    "apps.tenant_apps.loans.apps.LoansConfig",
    "apps.tenant_apps.rates",
    "apps.tenant_apps.notify_v2",
    "django_cleanup.apps.CleanupConfig",
]

INSTALLED_APPS = list(SHARED_APPS)

# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django_htmx.middleware.HtmxMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # WhiteNoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "debug_toolbar.middleware.DebugToolbarMiddleware",  # Django Debug Toolbar
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # 🔒 SECURITY FIX: Using secure middleware with membership validation
    "apps.orgs.middleware_v2.SecureWorkspaceMiddleware",
    # Phase 2: Subscription validation (must come after MessageMiddleware)
    "django_project.middleware.SubscriptionValidationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # django-allauth
    "django_project.middleware.HtmxMessagesMiddleware",
]

# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "django_project.workspace_urls"
# ROOT_URLCONF = "django_project.urls"

# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "django_project.wsgi.application"

# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.orgs.context_processors.theme_processor",
                # UI/UX enhancements
                "django_project.context_processors.user_permissions",
                "django_project.context_processors.workspace_context",
                "django_project.context_processors.subscription_context",
                "django_project.context_processors.google_oauth_context",
            ],
        },
    },
]

# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}

DATABASE_ROUTERS = ()

# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# https://docs.djangoproject.com/en/dev/topics/i18n/
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
FORMAT_MODULE_PATH = "django_project.formats"
LANGUAGES = [
    ("en", "English"),
    ("hi", "Hindi"),
]

# https://docs.djangoproject.com/en/dev/ref/settings/#time-zone
TIME_ZONE = "Asia/Kolkata"

# https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-USE_I18N
USE_I18N = True

# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True

DATETIME_INPUT_FORMATS = ("%d-%m-%Y, %H:%M:%S.%f%z",)
DATETIME_INPUT_FORMATS += ("%Y-%m-%d, %H:%M %p",)
DATETIME_INPUT_FORMATS += ("%d-%m-%Y, %H:%M:%S",)
DATETIME_INPUT_FORMATS += ("%d/%m/%Y, %H:%M:%S",)
DATE_INPUT_FORMATS = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d-%m-%y",
    "%d/%m/%y",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = BASE_DIR / "staticfiles"

# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"

# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# https://whitenoise.readthedocs.io/en/latest/django.html
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    # "compressor.finders.CompressorFinder",
]

# django-crispy-forms
# https://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
# Capture by default. Activating external mail requires a deliberate deployment
# change and acceptance; never infer permission to send from stored credentials.
from django_project.email_configuration import email_settings

globals().update(email_settings(env))

# Platform queue uses a dedicated SES API transport. The shared Django backend
# remains capture-only unless separately configured; borrower mail is not enabled.
PLATFORM_EMAIL_ENABLED = env.bool("PLATFORM_EMAIL_ENABLED", default=False)
PLATFORM_EMAIL_BASE_URL = env("PLATFORM_EMAIL_BASE_URL", default="")
PLATFORM_EMAIL_SENDER_DOMAIN = env("PLATFORM_EMAIL_SENDER_DOMAIN", default="notify.rokkad.com")
PLATFORM_SES_REGION = env("PLATFORM_SES_REGION", default="ap-south-1")
PLATFORM_SES_ACCESS_KEY_ID = env("PLATFORM_SES_ACCESS_KEY_ID", default="")
PLATFORM_SES_SECRET_ACCESS_KEY = env("PLATFORM_SES_SECRET_ACCESS_KEY", default="")
PLATFORM_SES_CONFIGURATION_SET = env("PLATFORM_SES_CONFIGURATION_SET", default="")
PLATFORM_SES_ACCOUNT_ID = env("PLATFORM_SES_ACCOUNT_ID", default="")
PLATFORM_SES_TOPIC_ARN = env("PLATFORM_SES_TOPIC_ARN", default="")
PLATFORM_SES_EVENTS_QUEUE_URL = env("PLATFORM_SES_EVENTS_QUEUE_URL", default="")

# Notify v2 WhatsApp delivery uses Meta's Cloud API exclusively. SMS remains
# fail-closed until a separate provider is deliberately selected.
WHATSAPP_CLOUD_API_VERSION = env("WHATSAPP_CLOUD_API_VERSION", default="v20.0")
WORKSPACE_SECRET_ENCRYPTION_KEY = env("WORKSPACE_SECRET_ENCRYPTION_KEY", default="")
# ADMINS = [('Admin', 'admin@example.com')]


# Function to parse ADMINS from environment variable
def parse_admins(admins_str):
    admins = []
    for admin in admins_str.split(","):
        name, email = admin.strip().split("<")
        email = email.strip(">")
        admins.append((name.strip(), email.strip()))
    return admins


# Parse ADMINS from environment variable
ADMINS = parse_admins(env("ADMINS"))

# django-debug-toolbar
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html
# https://docs.djangoproject.com/en/dev/ref/settings/#internal-ips
INTERNAL_IPS = ["127.0.0.1"]

# https://docs.djangoproject.com/en/dev/topics/auth/customizing/#substituting-a-custom-user-model
AUTH_USER_MODEL = "accounts.CustomUser"

# django-allauth config
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1

# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "home"

# https://django-allauth.readthedocs.io/en/latest/views.html#logout-account-logout
ACCOUNT_LOGOUT_REDIRECT_URL = "home"

# https://django-allauth.readthedocs.io/en/latest/installation.html?highlight=backends
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",  # Default
    "allauth.account.auth_backends.AuthenticationBackend",
)

# https://django-allauth.readthedocs.io/en/latest/configuration.html
# ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGIN_METHOD = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "optional"  # optional: unverified users can still login; mandatory: requires email confirmation
SOCIALACCOUNT_LOGIN_ON_GET = True

INVITATIONS_INVITATION_MODEL = "orgs.CompanyInvitation"
# INVITATIONS_INVITE_FORM = "apps.orgs.forms.InviteForm"
INVITATIONS_INVITE_FORM = "apps.orgs.forms.CompanyInvitationForm"
INVITATIONS_ADMIN_ADD_FORM = "apps.orgs.forms.InvitationAdminAddForm"
ACCOUNT_ADAPTER = "apps.platform_mail.adapter.AccountAdapter"
ACCOUNT_EMAIL_ENABLED = env.bool("ACCOUNT_EMAIL_ENABLED", default=False)
INVITATIONS_ADAPTER = ACCOUNT_ADAPTER

PHONENUMBER_DEFAULT_REGION = "IN"
PHONENUMBER_DEFAULT_FORMAT = "NATIONAL"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)

CACHES = {
    "default": env.cache_url("CACHE_URL", default="locmemcache://rokkad"),
}

# Borrower autocomplete uses signed URL-bound tokens, not cached widget state.
SELECT2_CACHE_BACKEND = "default"

CURRENCIES = ("USD", "INR", "AUD")
DEFAULT_CURRENCY = "INR"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "OAUTH_PKCE_ENABLED": True,
        "FETCH_USERINFO": True,
        "CLIENT_ID": env("GOOGLE_CLIENT_ID", default=""),  # Read from .env; empty string in dev
    }
}

# Sets the minimum message level that will be recorded by the messages framework
# https://docs.djangoproject.com/en/4.1/ref/settings/#message-level
MESSAGE_LEVEL = messages.DEBUG

# This sets the mapping of message level to message tag, which is typically rendered as a CSS class in HTML.
# https://docs.djangoproject.com/en/4.1/ref/settings/#message-tags
MESSAGE_TAGS = {
    messages.DEBUG: "bg-light",
    messages.INFO: "text-white bg-primary",
    messages.SUCCESS: "text-white bg-success",
    messages.WARNING: "text-dark bg-warning",
    messages.ERROR: "text-white bg-danger",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(name)s %(message)s"
        },
        "simple": {
            "format": "%(levelname)s %(asctime)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# USE_THOUSAND_SEPARATOR = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================================
# Razorpay Payment Gateway Configuration
# ============================================================================
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="test_key_id")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="test_key_secret")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")
BILLING_PROVIDER_MODE = env("BILLING_PROVIDER_MODE", default="disabled")

# Billing Configuration
BILLING_TAX_RATE = env("BILLING_TAX_RATE", default="")  # Explicit commercial review required.
BILLING_SELLER_NAME = env("BILLING_SELLER_NAME", default="")
BILLING_SELLER_ADDRESS = env("BILLING_SELLER_ADDRESS", default="")
BILLING_SELLER_TAX_STATUS = env("BILLING_SELLER_TAX_STATUS", default="")
BILLING_ALLOW_TRIAL_START = env.bool("BILLING_ALLOW_TRIAL_START", default=DEBUG)
BILLING_PUBLIC_TRIAL_PLAN_ID = env.int("BILLING_PUBLIC_TRIAL_PLAN_ID", default=0)
SUBSCRIPTION_GRACE_DAYS = 7
# Enable only after provider checkout/webhook acceptance on the deployment.
BILLING_CHECKOUT_ENABLED = env.bool("BILLING_CHECKOUT_ENABLED", default=False)
# Explicit new agreement/authorization gate; configured recovery remains available when paused.
BILLING_RECURRING_ENABLED = env.bool("BILLING_RECURRING_ENABLED", default=False)
# Selecting one reviewed binding publishes owner self-service; zero keeps the pilot private.
BILLING_PUBLIC_RECURRING_BINDING_ID = env.int("BILLING_PUBLIC_RECURRING_BINDING_ID", default=0)

THOUSAND_SEPARATOR = ","
DECIMAL_SEPARATOR = "."
