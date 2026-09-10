FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY consumer/worker.py /app/worker.py
ENV PYTHONPATH=/app/backend

CMD ["python", "/app/worker.py"]
