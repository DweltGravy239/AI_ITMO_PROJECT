# Минимальный контейнер для запуска PoC (опционально; основной путь — локальный python).
FROM python:3.11-slim
WORKDIR /app
COPY . /app
CMD ["python", "demo.py"]
