FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WDOS_ENVIRONMENT=staging

WORKDIR /app
COPY app.py ./app.py

EXPOSE 8000
CMD ["python", "app.py"]
