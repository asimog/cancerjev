FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md alembic.ini ./
COPY apps apps
COPY packages packages
COPY workers workers
COPY scientific scientific
COPY migrations migrations
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
