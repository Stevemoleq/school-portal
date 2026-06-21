import sys
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import dj_database_url
import os

load_dotenv()

import django.template.context
def patched_copy(self):
    duplicate = type(self).__new__(type(self))
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate
django.template.context.BaseContext.__copy__ = patched_copy

BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY
DEBUG = os.getenv("DEBUG", "False") == "True"

SECRET_KEY = os.getenv("SECRET_KEY")

# Validate SECRET_KEY at startup — never silently accept the dev default.
# In DEBUG, allow the well-known dev key so local work continues, but warn.
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-key"
        print(
            "WARNING: Using insecure development SECRET_KEY. "
            "Set SECRET_KEY in .env before any non-development use.",
            file=sys.stderr,
        )
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY must be set in the environment. "
            "Generate one with: "
            "python -c 'from django.core.management.utils import "
            "get_random_secret_key; print(get_random_secret_key())'"
        )

ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
]
if not ALLOWED_HOSTS:
    if DEBUG:
        ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    else:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS must be set in production. "
            "Set it to a comma-separated list of allowed Host headers, e.g. "
            "ALLOWED_HOSTS=myschool.example.com,www.myschool.example.com"
        )


# APPLICATIONS
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "apps.core",
    "apps.accounts",
    "apps.results",
    "apps.announcements",
    "apps.school",
    "apps.parents",
    "apps.fees",

    "import_export",
]


# MIDDLEWARE
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    
    "apps.core.logging_middleware.RequestLoggingMiddleware",
]


ROOT_URLCONF = "school_portal.urls"


# TEMPLATES
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.notification_context",
            ],
        },
    },
]


WSGI_APPLICATION = "school_portal.wsgi.application"


# DATABASE
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True
        )
    }
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "school_portal"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "school_portal"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5433"),
        }
    }


# AUTHENTICATION
AUTHENTICATION_BACKENDS = [
    "apps.accounts.auth_backends.StudentIDAuthBackend",
    "apps.parents.auth_backends.ParentPhoneAuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]


# PASSWORD VALIDATION
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# INTERNATIONALIZATION
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True


# MEDIA FILES
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# STATIC FILES
STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

if 'test' in sys.argv:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# LOGIN
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard_redirect"


# EMAIL SETTINGS
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "noreply@nazareneschool.com"
)


# LOGGING CONFIGURATION
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'detailed': {
            'format': '[{levelname}] {asctime} | {name} | {funcName}:{lineno} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'school_portal.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'apps.accounts': {
            'handlers': ['console', 'file', 'security_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.core': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.results': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.announcements': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.school': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.parents': {
            'handlers': ['console', 'file', 'security_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.fees': {
            'handlers': ['console', 'file', 'security_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)


# SECURITY SETTINGS
if not DEBUG:

    # CSRF_TRUSTED_ORIGINS: list the exact https origins that may POST
    # to this app. Wildcards are intentionally NOT supported by Django's
    # CSRF machinery, which prevents cross-origin abuse.
    csrf_trusted = [
        o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
    ]
    CSRF_TRUSTED_ORIGINS = csrf_trusted or [
        f"https://{h}" for h in ALLOWED_HOSTS if not h.startswith(".")
    ]

    # Trust a single X-Forwarded-Proto hop in front of the app.
    # If you have multiple proxy layers, set SECURE_PROXY_SSL_HEADER_NAME
    # to the actual header your outermost proxy uses.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    CSRF_COOKIE_HTTPONLY = True

# Session security — apply in all environments
SESSION_COOKIE_AGE = 28800  # 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
FILE_UPLOAD_PERMISSIONS = 0o644


# JAZZMIN CONFIG
JAZZMIN_SETTINGS = {
    # Brand details
    "site_title": "Nazarene School Portal",
    "site_header": "School Admin Portal",
    "site_brand": "Nazarene School",
    "welcome_sign": "Welcome to the Nazarene School Portal Admin panel",
    "copyright": "Nazarene Secondary School",
    
    # User / Search configurations
    "search_model": ["auth.User", "accounts.Student"],
    "user_avatar": None,

    # Side Navigation & UI
    "show_sidebar": True,
    "navigation_expanded": False,
    "hide_apps": [],
    "hide_models": [],
    
    # Custom icons for your apps (uses FontAwesome icons)
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "accounts.Student": "fas fa-user-graduate",
        "accounts.Teacher": "fas fa-chalkboard-teacher",
        "accounts.Class": "fas fa-school",
        "accounts.Subject": "fas fa-book",
        "parents.Parent": "fas fa-user-friends",
        "parents.Attendance": "fas fa-calendar-check",
        "results.Result": "fas fa-poll",
        "fees.Receipt": "fas fa-receipt",
        "fees.Accountant": "fas fa-file-invoice-dollar",
        "announcements.Announcement": "fas fa-bullhorn",
    },
    
    # Order of apps in the sidebar
    "order_with_respect_to": ["accounts", "parents", "results", "fees", "announcements", "auth"],
    
    # Related links in top menu
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "School Dashboard", "url": "/accounts/dashboard-redirect/", "new_window": True},
    ],
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "dark_mode_theme": "darkly",
}

# FEE REGISTRATION THRESHOLD — minimum fraction of fees that must be paid
# before a student can register for subjects (e.g., 0.5 = 50%).
FEE_REGISTRATION_THRESHOLD = 0.5

# DEFAULT PRIMARY KEY
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"