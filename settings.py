import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get("POSTGRES_DB"),
        'USER': os.environ.get("POSTGRES_USER"),
        'PASSWORD': os.environ.get("POSTGRES_PASSWORD"),
        'HOST': os.environ.get("POSTGRES_HOST"),
        'PORT': os.environ.get("POSTGRES_PORT")
    }
}
INSTALLED_APPS = (
    'data',
)

SECRET_KEY = os.environ.get("SECRET_KEY", '7(g+=fm&y-nqklfjulx1ss=aa&oixu=wid868r$2l$#$b@w+$f')
