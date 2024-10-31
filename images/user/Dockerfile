FROM python:3.11-slim

ARG DAGSTER_VERSION=1.8.13

RUN pip install -U uv
RUN python -m uv pip install \
    dagster==${DAGSTER_VERSION} \
    dagster-postgres \
    dagster-aws \
    dagster-k8s \
    dagster-celery[flower,redis,kubernetes] \
    dagster-celery-k8s

COPY example_project/ /