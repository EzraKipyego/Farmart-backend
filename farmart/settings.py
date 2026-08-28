import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured

load_dotenv()


def env_value(name, default=""):
    value = os.getenv(name, default).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env_value("DJANGO_SECRET_KEY", "dev-secret-change-me")
DEBUG = env_value("DEBUG", "True").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "accounts",
    "animals",
    "orders",
    "payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "farmart.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "farmart.wsgi.application"

database_url = env_value("DATABASE_URL")
if not database_url and not DEBUG:
    raise ImproperlyConfigured("DATABASE_URL must be set when DEBUG=False")

DATABASES = {
    "default": dj_database_url.config(
        default=database_url or (
            f"postgresql://{env_value('DB_USER', 'farmart_user')}:{env_value('DB_PASSWORD', 'farmart_pass')}"
            f"@{env_value('DB_HOST', 'localhost')}:{env_value('DB_PORT', '5432')}"
            f"/{env_value('DB_NAME', 'farmart_db')}"
        ),
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "EXCEPTION_HANDLER": "farmart.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
}

CORS_ALLOWED_ORIGINS = [
    env_value("FRONTEND_ORIGIN", env_value("FRONTEND_URL", "http://localhost:5173")),
]
CORS_ALLOW_HEADERS = [
    *default_headers,
    "idempotency-key",
]
CORS_ALLOW_CREDENTIALS = True

# Daraja (M-Pesa) sandbox credentials. Leave blank during development —
# the payments app falls back to a simulated STK push until these are
# set, so the full flow still works end to end without them.
DARAJA_CONSUMER_KEY = env_value("MPESA_CONSUMER_KEY", env_value("DARAJA_CONSUMER_KEY"))
DARAJA_CONSUMER_SECRET = env_value("MPESA_CONSUMER_SECRET", env_value("DARAJA_CONSUMER_SECRET"))
DARAJA_SHORTCODE = env_value("MPESA_SHORTCODE", env_value("DARAJA_SHORTCODE"))
DARAJA_PASSKEY = env_value("MPESA_PASSKEY", env_value("DARAJA_PASSKEY"))
DARAJA_CALLBACK_URL = env_value("MPESA_CALLBACK_URL", env_value("DARAJA_CALLBACK_URL")).rstrip("/")
DARAJA_ENV = env_value(
    "MPESA_ENVIRONMENT",
    env_value("MPESA_ENV", env_value("DARAJA_ENV", "sandbox")),
).lower()

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"