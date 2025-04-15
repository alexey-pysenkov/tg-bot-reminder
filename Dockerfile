FROM python:3.10-slim

# Установка зависимостей для локали
RUN apt-get update && apt-get install -y locales && rm -rf /var/lib/apt/lists/*

# Установка и генерация локали
RUN echo "ru_RU.UTF-8 UTF-8" > /etc/locale.gen && locale-gen
ENV LANG=ru_RU.UTF-8
ENV LANGUAGE=ru_RU:ru
ENV LC_ALL=ru_RU.UTF-8

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создание директории для логов и временных файлов
RUN mkdir -p /app/logs
RUN mkdir -p /app/tmp

# Устанавливаем права на папку database
RUN mkdir -p /app/database && chmod 777 /app/database

CMD ["python", "bot.py"]