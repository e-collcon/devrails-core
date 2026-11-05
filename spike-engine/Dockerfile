# spike-engine container (BR-05, TASK-114/115). No credentials are baked in:
# at runtime the job uses its service account's ADC, or a Secret Manager key
# mounted as a file and referenced by GOOGLE_APPLICATION_CREDENTIALS.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd --system --uid 10001 engine

COPY config.py main.py ./
COPY engine/ engine/

USER engine
# One process run = one poll cycle; exit code tells Cloud Run Jobs whether it succeeded.
ENTRYPOINT ["python", "main.py"]
