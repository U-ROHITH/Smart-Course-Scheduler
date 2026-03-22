from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ──────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-local-dev-only-change-in-prod')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# ── Application ───────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # serves static files
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'scheduler.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'scheduler.wsgi.application'

# ── Database ──────────────────────────────────────────────────────────────────
# Not used at runtime (no models are read/written in production).
# Kept so `manage.py` commands don't error.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/tmp/db.sqlite3',
    }
}

# ── Cache ─────────────────────────────────────────────────────────────────────
# LocMemCache: in-process, per-invocation. Good enough to de-duplicate YouTube
# API calls within a single request; no persistent disk required.

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ── Internationalisation ──────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True

# ── Static files ──────────────────────────────────────────────────────────────
# WhiteNoise serves compressed static files directly from Django.
# `collectstatic` writes to STATIC_ROOT; build_files.sh copies to Vercel CDN.

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── API keys ──────────────────────────────────────────────────────────────────

YOUTUBE_API_KEY   = os.getenv('YOUTUBE_API_KEY', '')
GOOGLE_CLIENT_ID  = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

# ── Misc ──────────────────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
