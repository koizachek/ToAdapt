FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-Root; Schreibrechte nur dort, wo Datei-Fallbacks und der Case-Pool liegen.
RUN useradd --create-home appuser \
    && mkdir -p backend/db/runtime_submissions backend/db/submissions \
    && chown -R appuser:appuser /app/backend/db /app/backend/cases/pool
USER appuser

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
