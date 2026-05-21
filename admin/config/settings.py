from pathlib import Path
import os

from dotenv import load_dotenv
from django.urls import reverse_lazy


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "rest_framework",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "learning",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Asia/Tomsk")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
}

UNFOLD = {
    "SITE_TITLE": "RouteCraft Admin",
    "SITE_HEADER": "RouteCraft",
    "SITE_SUBHEADER": "Персонализированные образовательные маршруты",
    "SITE_SYMBOL": "route",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "learning.admin.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Маршруты",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Курсы",
                        "icon": "school",
                        "link": reverse_lazy("admin:learning_course_changelist"),
                    },
                    {
                        "title": "Модули",
                        "icon": "view_module",
                        "link": reverse_lazy("admin:learning_coursemodule_changelist"),
                    },
                    {
                        "title": "Элементы модулей",
                        "icon": "library_books",
                        "link": reverse_lazy("admin:learning_moduleelement_changelist"),
                    },
                ],
            },
            {
                "title": "Материалы",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Материалы",
                        "icon": "link",
                        "link": reverse_lazy("admin:learning_learningmaterial_changelist"),
                    },
                    {
                        "title": "Кандидаты поиска",
                        "icon": "travel_explore",
                        "link": reverse_lazy("admin:learning_materialcandidate_changelist"),
                    },
                    {
                        "title": "Обратная связь",
                        "icon": "thumbs_up_down",
                        "link": reverse_lazy("admin:learning_materialfeedback_changelist"),
                    },
                ],
            },
            {
                "title": "LLM и Web Search",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "DEFAULT_LLM",
                        "icon": "tune",
                        "link": reverse_lazy("admin:learning_llmsettings_changelist"),
                    },
                    {
                        "title": "WEB_SEARCH",
                        "icon": "manage_search",
                        "link": reverse_lazy("admin:learning_websearchprofile_changelist"),
                    },
                    {
                        "title": "Запуски pipeline",
                        "icon": "account_tree",
                        "link": reverse_lazy("admin:learning_pipelinerun_changelist"),
                    },
                ],
            },
            {
                "title": "Пользователи",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Профили",
                        "icon": "person",
                        "link": reverse_lazy("admin:learning_learnerprofile_changelist"),
                    },
                    {
                        "title": "Сертификаты",
                        "icon": "workspace_premium",
                        "link": reverse_lazy("admin:learning_certificate_changelist"),
                    },
                ],
            },
        ],
    },
}
