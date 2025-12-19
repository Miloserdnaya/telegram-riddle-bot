#!/bin/bash
# Скрипт для запуска бота

cd /Users/afinamiloserdnaya/ripple

# Активируем Python окружение если есть
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/Library/Python/3.9/bin:$PATH"

# Запускаем бота
exec /usr/bin/python3 bot.py

