# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

 CMD ["chainlit", "run", "app.py", "--port", "8000", "--host", "0.0.0.0"]