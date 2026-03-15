from .base import *  # noqa
import os
import dj_database_url

# --- Core ---
DEBUG = False
SECRET_KEY = env("SECRET_KEY")

# Auto-include Railway domain — no manual ALLOWED_HOSTS needed
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_domain and railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(railway_domain)
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]

# --- Database ---
DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# --- Static Files ---
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- Cloudinary Media Storage ---
import cloudinary
import cloudinary.uploader
import cloudinary.api

INSTALLED_APPS += ["cloudinary_storage", "cloudinary"]

CLOUDINARY_STORAGE = {
    "CLOUDINARY_URL": env("CLOUDINARY_URL")
}

DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
MEDIA_URL = "/media/"

# --- File Upload Limits ---
MAX_UPLOAD_SIZE_MB = 20
ALLOWED_DOCUMENT_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
]

# --- Security Headers ---
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# --- CORS ---
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
# Auto-include Railway domain in CORS
if railway_domain:
    railway_url = f"https://{railway_domain}"
    if railway_url not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(railway_url)
CORS_ALLOW_CREDENTIALS = True

# --- Celery (inherit Redis URL from Railway) ---
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}