# Настройка Google Sheets для записи грантов

## Шаг 1: Создание Google Cloud проекта

1. Перейдите на https://console.cloud.google.com/
2. Создайте новый проект или выберите существующий
3. Включите Google Sheets API и Google Drive API

## Шаг 2: Создание Service Account

1. Перейдите в "IAM & Admin" → "Service Accounts"
2. Нажмите "Create Service Account"
3. Заполните имя и описание
4. Нажмите "Create and Continue"
5. Нажмите "Done"

## Шаг 3: Создание ключа

1. Откройте созданный Service Account
2. Перейдите на вкладку "Keys"
3. Нажмите "Add Key" → "Create new key"
4. Выберите формат JSON
5. Скачайте файл и сохраните как `credentials.json` в корне проекта

## Шаг 4: Создание Google Sheets таблицы

1. Создайте новую таблицу в Google Sheets
2. Скопируйте ID таблицы из URL (между `/d/` и `/edit`)
   Например: `https://docs.google.com/spreadsheets/d/1ABC123.../edit`
   ID: `1ABC123...`
3. Поделитесь таблицей с email из `credentials.json` (поле `client_email`)
4. Дайте права "Редактор"

## Шаг 5: Настройка переменных окружения

Добавьте в файл `.env`:
```
GOOGLE_SHEET_ID=ваш_id_таблицы
GOOGLE_CREDENTIALS_FILE=credentials.json
```

## Важно

- Файл `credentials.json` должен быть в корне проекта
- Не коммитьте `credentials.json` в git (он уже в .gitignore)
- Таблица будет автоматически создана с листом "Гранты" при первом использовании

