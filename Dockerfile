# syntax=docker/dockerfile:1.7

# Use MCR base image to avoid Docker Hub pull rate limits in ACR builds.
FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY scripts ./scripts

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install .

RUN useradd --create-home --uid 10001 appuser
USER 10001

EXPOSE 8000

CMD ["uvicorn", "chatbot_parking.web_demo_server:app", "--host", "0.0.0.0", "--port", "8000"]
