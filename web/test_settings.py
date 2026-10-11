from .settings import *  # noqa

# disable whitenoise so we don't have to collectstatic for tests
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
MIDDLEWARE_REMOVE = ["whitenoise.middleware.WhiteNoiseMiddleware"]
MIDDLEWARE = [m for m in MIDDLEWARE if m not in MIDDLEWARE_REMOVE]  # noqa
