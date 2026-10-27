FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 8 --timeout 600 --keep-alive 10
