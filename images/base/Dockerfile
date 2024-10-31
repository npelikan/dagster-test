FROM python:3.11-slim

ARG DAGSTER_VERSION=1.8.13

# All packages are hard-pinned to `dagster`, so setting the version on just `DAGSTER` will ensure
# compatible versions.
RUN pip install -U uv
RUN ython -m uv pip install \
    dagster==${DAGSTER_VERSION} \
    dagster-azure \
    dagster-postgres \
    dagster-k8s \
    dagster-aws \
    dagster-celery[flower,redis,kubernetes] \
    dagster-celery-k8s \
    dagster-gcp \
    dagster-graphql \
    dagster-webserver