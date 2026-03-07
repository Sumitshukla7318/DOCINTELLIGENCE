import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "django_celery_results",
    "django_celery_beat",
]

LOCAL_APPS = [
    "apps.users",
    "apps.documents", 
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",          # Must be before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

# --- Database ---
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")
}

# --- Custom User Model ---
AUTH_USER_MODEL = "users.User"

# --- Password Validation ---
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalization ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "static/"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
}

# --- SimpleJWT ---
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,         # New refresh token on each use
    "BLACKLIST_AFTER_ROTATION": True,      # Old refresh token invalidated
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": "apps.users.serializers.CustomTokenObtainPairSerializer",
}

# --- drf-spectacular ---
SPECTACULAR_SETTINGS = {
    "TITLE": "Document Intelligence API",
    "DESCRIPTION": """
## Overview
A production-grade AI-powered document processing API.

Upload PDF or image documents and get back:
- **Summaries** — 3-5 bullet point summaries via Groq/Llama
- **Entity Extraction** — people, organizations, dates, locations
- **Document Q&A** — ask any question, get answers grounded in your document

## Authentication
This API uses **JWT Bearer tokens**.

1. Register at `/api/v1/auth/register/`
2. Login at `/api/v1/auth/login/` to get your `access` token
3. Pass it as: `Authorization: Bearer <access_token>`
4. Refresh expired tokens at `/api/v1/auth/token/refresh/`

## Rate Limiting
- **10 uploads per minute** per user
- **20 uploads per day** per user (configurable per account)
- Rate limit errors return `HTTP 429`

## Webhook Support
Optionally provide a `webhook_url` when uploading a document.
We'll POST a signed payload to that URL when processing completes.
Verify the signature using the `X-Webhook-Signature` header (HMAC-SHA256).

## Document Processing Flow
Upload → PENDING → PROCESSING → COMPLETED
                             ↘ FAILED (retried up to 3x)
    """,
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1/",
    "SORT_OPERATIONS": False,
    "TAGS": [
        {"name": "Auth", "description": "Registration, login, logout, profile management"},
        {"name": "Documents", "description": "Upload, retrieve, delete, and query documents"},
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": False,
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
        "docExpansion": "list",
        "filter": True,
        "syntaxHighlight.theme": "monokai",
    },
    "SWAGGER_UI_FAVICON_HREF": "https://www.djangoproject.com/favicon.ico",
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
    ],
}

# --- CORS ---
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- File Upload Limits ---
MAX_UPLOAD_SIZE_MB = 20
ALLOWED_DOCUMENT_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"]

# --- Celery ---
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"        # Store results in PostgreSQL via django-celery-results
CELERY_CACHE_BACKEND = "django-cache"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True           # Task shows 'STARTED' state, not just PENDING
CELERY_TASK_TIME_LIMIT = 30 * 60          # Hard kill after 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60     # Raises SoftTimeLimitExceeded at 25 min — lets us clean up gracefully
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50    # Restart worker process every 50 tasks — prevents memory leaks
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True


# --- Groq (free OpenAI-compatible API) ---
GROQ_API_KEY = env("GROQ_API_KEY", default="")
GROQ_MODEL = env("GROQ_MODEL", default="llama-3.1-8b-instant")
GROQ_MAX_TOKENS = env.int("GROQ_MAX_TOKENS", default=1000)


# --- Rate Limiting ---
# Uses Redis as the rate limit counter backend
RATELIMIT_USE_CACHE = "default"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
    }
}

# Upload limits per user
DAILY_UPLOAD_LIMIT = env.int("DAILY_UPLOAD_LIMIT", default=20)

# Webhook settings
WEBHOOK_TIMEOUT_SECONDS = env.int("WEBHOOK_TIMEOUT_SECONDS", default=10)
WEBHOOK_MAX_RETRIES = env.int("WEBHOOK_MAX_RETRIES", default=3)

RATELIMIT_VIEW = "apps.documents.views.handle_ratelimited"