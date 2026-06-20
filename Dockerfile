FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -e .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "wattscheduler.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
