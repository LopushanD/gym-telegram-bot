FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install "python-telegram-bot>=21.0,<22.0" --no-cache-dir

COPY main.py .
COPY src ./src

CMD ["python", "main.py"]
