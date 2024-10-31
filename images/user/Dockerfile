FROM python3.11-slim

ARG DAGSTER_VERSION=1.8.13

COPY build_cache/ /

RUN pip install \
    -e dagster \
    -e dagster-pipes \
    -e dagster-postgres \
    -e dagster-celery[flower,redis,kubernetes] \
    -e dagster-aws \
    -e dagster-k8s \
    -e dagster-celery-k8s

COPY example_project/ /