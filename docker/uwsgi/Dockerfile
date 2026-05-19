FROM python:3.9
LABEL maintainer="James Turk <dev@jamesturk.net>"

ARG UID=999

# global environment settings
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONIOENCODING='utf-8' \
  LANG='C.UTF-8'
STOPSIGNAL SIGINT

RUN apt-get --allow-releaseinfo-change update -qq \
    && apt-get install -y --no-install-recommends -qq \
        postgresql-client \
        uwsgi \
        libpq5 \
        libgdal36 \
        libpcre2-8-0 \
        python3-dev \
        git \
        build-essential \
        libpq-dev \
        libgeos-dev \
        libgdal-dev \
        libcap-dev \
        libpcre2-dev \
        uwsgi-src \
        awscli \
        curl \
        gnupg \
    && cd /usr/lib/uwsgi/plugins \
    && uwsgi --build-plugin "/usr/src/uwsgi/plugins/python python39"

# copy code
ADD . /code/
WORKDIR /code/
COPY docker/uwsgi/custom-entrypoint /usr/local/bin
COPY docker/uwsgi/node.pin /etc/apt/preferences.d/node

RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENV NODE_OPTIONS=--openssl-legacy-provider  
RUN npm ci \
    && npm run build \
    && rm -rf node_modules
RUN pip --no-cache-dir --disable-pip-version-check install poetry wheel

# install poetry deps as root user but chown to openstates user 
# (install virtual environment in project folder so that openstates user can access)
RUN poetry config virtualenvs.in-project true \
    && poetry install --without dev \
    && rm -r ~/.cache/pypoetry/cache ~/.cache/pypoetry/artifacts/
RUN useradd -u $UID -Ulmr -d /home/openstates openstates \
    && chown -R openstates:openstates /code

RUN apt-get remove -y -qq build-essential \
      gcc \
      g++ \
      make \
      python3-dev \
      git \
      libpq-dev \
      libgeos-dev \
      libgdal-dev \
      libcap-dev \
      libpcre2-dev \
      uwsgi-src \
    && apt-get autoremove -y

USER openstates:openstates

# uwsgi config
ENV UWSGI_MASTER=1 \
  UWSGI_HTTP_AUTO_CHUNKED=1 \
  UWSGI_HTTP_KEEPALIVE=1 \
  UWSGI_LAZY_APPS=1 \
  UWSGI_WSGI_ENV_BEHAVIOR=holy \
  UWSGI_MODULE=web.wsgi:application \
  UWSGI_BUFFER_SIZE=8096 \
  UWSGI_HARAKIRI=30 \
  UWSGI_SINGLE_INTERPRETER=1 \
  UWSGI_PLUGIN=python39 \
  UWSGI_SOCKET=:9999

ENTRYPOINT ["custom-entrypoint"]
CMD ["uwsgi", "--show-config"]
