import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url
from corsheaders.defaults import default_headers

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-change-me")
DEBUG = os.environ.get("DEBUG", "True") == "True"
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

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get(
            "DATABASE_URL", "postgresql://farmart_user:farmart_pass@localhost:5432/farmart_db"
        )
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
    os.environ.get("FRONTEND_ORIGIN", os.environ.get("FRONTEND_URL", "http://localhost:5173")),
]
CORS_ALLOW_HEADERS = [
    *default_headers,
    "idempotency-key",
]
CORS_ALLOW_CREDENTIALS = True

# Daraja (M-Pesa) sandbox credentials. Leave blank during development —
# the payments app falls back to a simulated STK push until these are
# set, so the full flow still works end to end without them.
DARAJA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY", os.environ.get("DARAJA_CONSUMER_KEY", ""))
DARAJA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET", os.environ.get("DARAJA_CONSUMER_SECRET", ""))
DARAJA_SHORTCODE = os.environ.get("MPESA_SHORTCODE", os.environ.get("DARAJA_SHORTCODE", ""))
DARAJA_PASSKEY = os.environ.get("MPESA_PASSKEY", os.environ.get("DARAJA_PASSKEY", ""))
DARAJA_CALLBACK_URL = os.environ.get("MPESA_CALLBACK_URL", os.environ.get("DARAJA_CALLBACK_URL", ""))
DARAJA_ENV = os.environ.get("MPESA_ENV", os.environ.get("DARAJA_ENV", "sandbox"))

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"