FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install deps first so this layer caches across source-only changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

# VERSION is surfaced to the app (and shown in the GUI) at runtime.
ARG VERSION=dev
ENV VERSION=${VERSION}

# Run as the same non-root uid the Helm chart's securityContext expects.
RUN useradd --uid 65532 --no-create-home --user-group appuser
USER 65532:65532

EXPOSE 8080
# One worker per pod keeps Prometheus counters consistent (each worker has its
# own metrics registry); horizontal scale comes from the chart's replicaCount.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "app:app"]
