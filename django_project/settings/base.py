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
    "django_tenants",  # mandatory
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
    "dynamic_preferences",
    "django_htmx",
    "import_export",
    "colorfield",
    "guardian",  # Object-level permissions
    # Local
    "accounts",
    "apps.onboarding",  # User onboarding flow
    "apps.subscriptions",
    "pages",
    "invitations",
    "slick_reporting",
    "django_cleanup.apps.CleanupConfig",
    "viewflow",
]

TENANT_APPS = [
    "apps.tenant_apps.approval",
    "apps.tenant_apps.contact",
    "apps.tenant_apps.girvi",
    "apps.tenant_apps.product",
    "apps.tenant_apps.terms",
    "apps.tenant_apps.rates",
    "apps.tenant_apps.notify",
    "apps.tenant_apps.notify_v2",
    "apps.tenant_apps.dea",
    "apps.tenant_apps.purchase",
    "apps.tenant_apps.sales",
]

INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

TENANT_MODEL = "orgs.Company"  # app.Model

TENANT_DOMAIN_MODEL = "orgs.Domain"  # app.Model

# Controlled rollout flag for automatic tenant baseline seeding on workspace create.
TENANT_AUTO_SEED_ON_CREATE = env.bool("TENANT_AUTO_SEED_ON_CREATE", default=False)

# Clone mode for onboarding template provisioning.
# Recommended for clone+seed workflow: NODATA (clone structure, seed via commands).
ONBOARDING_TEMPLATE_CLONE_MODE = env(
    "ONBOARDING_TEMPLATE_CLONE_MODE",
    default="NODATA",
)

# Performance: avoid repeated search_path SET calls when tenant is unchanged.
TENANT_LIMIT_SET_CALLS = True
ALLOW_COMPANY_HARD_DELETE=True
# Optional shared schemas visible to all tenants (for reference/master data).
# Configure via .env, e.g. PG_EXTRA_SEARCH_PATHS=shared_data
PG_EXTRA_SEARCH_PATHS = env.list("PG_EXTRA_SEARCH_PATHS", default=[])

SHOW_PUBLIC_IF_NO_TENANT_FOUND = True
# in case using domain to set tenants us this to persist sessions.for localhost search for workaround hint:edit hosts file
# SESSION_COOKIE_DOMAIN = '.rokkad.com'
# CSRF_COOKIE_DOMAIN = '.rokkad.com'

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
    # 🔒 SECURITY FIX: Using secure middleware with membership validation
    "apps.orgs.middleware_v2.SecureWorkspaceMiddleware",
    "apps.tenant_apps.rates.middleware.RateMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Phase 2: Subscription validation (must come after MessageMiddleware)
    "django_project.middleware.SubscriptionValidationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # django-allauth
    "django_project.middleware.HtmxMessagesMiddleware",
]

# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "django_project.tenant_urls"
PUBLIC_SCHEMA_URLCONF = "django_project.urls"
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
                "django_project.context_processors.navigation_config",
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
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# Ensure test database setup uses tenant-aware schema migration flow.
TEST_RUNNER = "django_project.test_runner.TenantAwareDiscoverRunner"

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
        "BACKEND": "django_tenants.files.storage.TenantFileSystemStorage",
        # "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATICFILES_FINDERS = [
    "django_tenants.staticfiles.finders.TenantFileSystemFinder",  # Must be first
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    # "compressor.finders.CompressorFinder",
]

# django-crispy-forms
# https://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")

# notify_v2 digital delivery adapters (Twilio + WhatsApp Cloud API)
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_FROM_NUMBER = env("TWILIO_FROM_NUMBER", default="")
TWILIO_WHATSAPP_FROM_NUMBER = env("TWILIO_WHATSAPP_FROM_NUMBER", default="")
NOTIFY_V2_TWILIO_STUB_FALLBACK = env.bool("NOTIFY_V2_TWILIO_STUB_FALLBACK", default=True)

# WhatsApp provider for notify_v2 channel dispatch: "twilio" or "cloud"
NOTIFY_V2_WHATSAPP_PROVIDER = env("NOTIFY_V2_WHATSAPP_PROVIDER", default="twilio")
WHATSAPP_CLOUD_API_VERSION = env("WHATSAPP_CLOUD_API_VERSION", default="v20.0")
WHATSAPP_CLOUD_PHONE_NUMBER_ID = env("WHATSAPP_CLOUD_PHONE_NUMBER_ID", default="")
WHATSAPP_CLOUD_ACCESS_TOKEN = env("WHATSAPP_CLOUD_ACCESS_TOKEN", default="")
WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN = env("WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN", default="")
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
    "guardian.backends.ObjectPermissionBackend",  # Guardian object permissions
    "allauth.account.auth_backends.AuthenticationBackend",
)

# Guardian settings
ANONYMOUS_USER_NAME = None
GUARDIAN_RENDER_403 = True
GUARDIAN_TEMPLATE_403 = "403.html"

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
ACCOUNT_ADAPTER = "invitations.models.InvitationsAdapter"
INVITATIONS_ADAPTER = "invitations.models.InvitationsAdapter"

PHONENUMBER_DEFAULT_REGION = "IN"
PHONENUMBER_DEFAULT_FORMAT = "NATIONAL"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_FUNCTION": "django_tenants.cache.make_key",
        "REVERSE_KEY_FUNCTION": "django_tenants.cache.reverse_key",
    },
    "select2": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}

# Set the cache backend to select2
SELECT2_CACHE_BACKEND = "select2"

SLICK_REPORTING_SETTINGS = {
    "CHARTS": {
        "apexcharts": {
            "entryPoint": "DisplayApexPieChart",
            "js": (
                "https://cdn.jsdelivr.net/npm/apexcharts",
                "slick_reporting/slick_reporting.chartsjs.js",
            ),
            "css": {
                "all": (
                    "https://cdn.jsdelivr.net/npm/apexcharts/dist/apexcharts.min.css",
                )
            },
        },
    },
}

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

MULTITENANT_RELATIVE_MEDIA_ROOT = "%s/"
MULTITENANT_STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "tenants/%s/static"),
]

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
    "filters": {
        "tenant_context": {
            "()": "django_tenants.log.TenantContextFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "[%(schema_name)s] %(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(name)s %(message)s"
        },
        "simple": {
            "format": "[%(schema_name)s] %(levelname)s %(asctime)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["tenant_context"],
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["tenant_context"],
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

# Billing Configuration
BILLING_TAX_RATE = env("BILLING_TAX_RATE", default="18")  # 18% GST for India

THOUSAND_SEPARATOR = ","
DECIMAL_SEPARATOR = "."
