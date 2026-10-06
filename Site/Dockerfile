FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код сайта
COPY . .

# Открываем порт для веб-панели
EXPOSE 5000

CMD ["python", "app.py"]