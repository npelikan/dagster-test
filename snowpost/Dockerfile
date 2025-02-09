FROM python:3.11-slim

ARG DAGSTER_VERSION=1.8.13

RUN pip install -U uv

COPY . /

RUN python -m uv pip install -r requirements.txt
