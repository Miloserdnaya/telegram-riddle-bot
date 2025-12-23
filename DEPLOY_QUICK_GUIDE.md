# 🚀 Быстрый гайд: GitHub → Railway

## Шаг 1: GitHub (5 минут)

### 1. Создайте репозиторий
- Откройте https://github.com/new
- Название: `telegram-riddle-bot`
- **НЕ** добавляйте README/.gitignore (уже есть)
- Нажмите **Create repository**

### 2. Загрузите код
```bash
cd /Users/afinamiloserdnaya/ripple

# Замените YOUR_USERNAME на ваш GitHub username
git remote add origin https://github.com/YOUR_USERNAME/telegram-riddle-bot.git
git branch -M main
git push -u origin main
```

**Если запросит авторизацию:**
- Username: ваш GitHub username
- Password: Personal Access Token (создайте на https://github.com/settings/tokens)

## Шаг 2: Railway (5 минут)

### 1. Регистрация
- Откройте https://railway.app
- Войдите через GitHub

### 2. Создание проекта
- **New Project** → **Deploy from GitHub repo**
- Выберите `telegram-riddle-bot`
- Railway автоматически начнет деплой

### 3. Добавьте переменные
В проекте → **Variables** → добавьте:
- `BOT_TOKEN` = `8552794244:AAEEMnwCkRmNWV8hC_wyU26B-0OUheHFZjc`

### 4. Готово! 🎉
Бот работает 24/7 на Railway!

## 📚 Подробные инструкции

- `GITHUB_SETUP.md` - детальная инструкция по GitHub
- `DEPLOY_RAILWAY.md` - детальная инструкция по Railway


