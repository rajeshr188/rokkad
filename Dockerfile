ARG PYTHON_IMAGE=python:3.14-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt requirements.lock ./
RUN pip wheel --wheel-dir /wheels -r requirements.txt -c requirements.lock

FROM ${PYTHON_IMAGE}
ARG ROKKAD_REVISION=unknown
LABEL org.opencontainers.image.revision=${ROKKAD_REVISION}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=django_project.settings.prod
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /var/www/rokkad/static /var/www/rokkad/media && chown -R app:app /var/www/rokkad
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
WORKDIR /code
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["python", "scripts/start_web.py", "gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "django_project.wsgi:application"]
