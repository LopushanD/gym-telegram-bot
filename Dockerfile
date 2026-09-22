FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install "python-telegram-bot>=21.0,<22.0" --no-cache-dir
RUN mkdir -p /app/data
COPY main.py .
#remove during development/tests for more convenient access to assets
#also look at volume for assets in the yml file
# COPY assets ./assets
COPY src ./src

CMD ["python", "main.py"]
