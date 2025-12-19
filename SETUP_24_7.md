# Настройка бота для работы 24/7

## ⚠️ Важно

Бот на вашем ноутбуке будет работать только когда ноутбук включен. Для работы 24/7 (даже когда ноутбук выключен) нужен удаленный сервер.

## Вариант 1: Автозапуск на вашем Mac (работает только когда Mac включен)

Бот уже настроен для автозапуска через launchd.

### Управление сервисом:

**Запустить бота:**
```bash
launchctl load ~/Library/LaunchAgents/com.riddle.bot.plist
# или
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.riddle.bot.plist
```

**Остановить бота:**
```bash
launchctl unload ~/Library/LaunchAgents/com.riddle.bot.plist
# или
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.riddle.bot.plist
```

**Проверить статус:**
```bash
launchctl list | grep riddle
```

**Просмотр логов:**
```bash
tail -f ~/ripple/bot.log
tail -f ~/ripple/bot.error.log
```

## Вариант 2: Облачный сервер для работы 24/7

Для работы бота 24/7 даже когда ваш ноутбук выключен, используйте:

### Рекомендуемые сервисы:

1. **Railway** (https://railway.app) - бесплатный тариф, простой деплой
2. **Heroku** (https://heroku.com) - бесплатный тариф
3. **DigitalOcean** (https://digitalocean.com) - от $5/месяц
4. **VPS от любого провайдера** - от $3-5/месяц

### Быстрый деплой на Railway:

1. Зарегистрируйтесь на railway.app
2. Создайте новый проект
3. Подключите GitHub репозиторий
4. Railway автоматически определит Python проект
5. Добавьте переменную окружения `BOT_TOKEN`
6. Бот будет работать 24/7

### Или используйте простой VPS:

1. Арендуйте VPS (например, на DigitalOcean)
2. Установите Python и зависимости
3. Загрузите код бота
4. Запустите через systemd или screen/tmux
5. Бот будет работать постоянно

## Текущая настройка

Бот настроен для автозапуска на вашем Mac через launchd. Он будет автоматически запускаться при включении компьютера и перезапускаться при сбоях.

