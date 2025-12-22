import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import random

import config
import database
import riddle_generator
import course_recommendations
import promo_generator
import google_sheets

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальный планировщик
scheduler = AsyncIOScheduler()


async def generate_new_riddle():
    """Генерировать новую загадку"""
    try:
        riddle = riddle_generator.get_random_riddle()
        riddle_id = await database.add_riddle(
            question=riddle["question"],
            answer=riddle["answer"],
            hint=riddle.get("hint")
        )
        logger.info(f"Сгенерирована новая загадка #{riddle_id}: {riddle['question']}")
        return riddle_id
    except Exception as e:
        logger.error(f"Ошибка при генерации загадки: {e}")
        return None


async def generate_daily_riddles():
    """Генерировать загадки на день (20 загадок)"""
    try:
        count = 0
        for _ in range(20):
            riddle_id = await generate_new_riddle()
            if riddle_id:
                count += 1
        logger.info(f"Сгенерировано {count} загадок на день")
    except Exception as e:
        logger.error(f"Ошибка при генерации ежедневных загадок: {e}")


async def update_weekly_ratings():
    """Очистить турнирную таблицу - сбросить рейтинг всех пользователей каждый понедельник в 00:00"""
    try:
        await database.reset_weekly_ratings()
        logger.info("✅ Турнирная таблица очищена: рейтинг всех пользователей сброшен до 1000")
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке турнирной таблицы: {e}", exc_info=True)


async def weekly_grant_raffle(context: ContextTypes.DEFAULT_TYPE):
    """Выдача грантов 30 000₽ топ-10 лидерам каждое воскресенье в 00:00"""
    try:
        # Получаем топ-10 лидеров
        leaders = await database.get_weekly_leaderboard(limit=10)
        
        if not leaders or len(leaders) == 0:
            logger.info("Нет лидеров для выдачи грантов")
            return
        
        # Получаем все существующие промокоды
        existing_codes = await database.get_all_promo_codes()
        
        # Фильтруем лидеров, которые еще не получали грант
        eligible_leaders = []
        for leader in leaders:
            has_received = await database.has_ever_received_grant(leader["user_id"])
            if not has_received:
                eligible_leaders.append(leader)
        
        if not eligible_leaders:
            logger.info("Все топ-10 лидеры уже получали грант ранее")
            return
        
        bot = context.bot
        granted_count = 0
        
        # Выдаем грант каждому подходящему лидеру
        for leader in eligible_leaders:
            try:
                leader_id = leader["user_id"]
                
                # Генерируем уникальный промокод
                promo_code = promo_generator.generate_unique_promo_code(existing_codes, prefix="BBE")
                existing_codes.append(promo_code)  # Добавляем в список, чтобы избежать дубликатов
                
                # Сохраняем победителя с промокодом в базу данных
                await database.save_grant_winner(leader_id, promo_code, grant_amount=30000)
                
                # Записываем в Google Sheets
                await google_sheets.add_grant_to_sheet(
                    user_id=leader_id,
                    username=leader.get("username"),
                    first_name=leader.get("first_name"),
                    promo_code=promo_code,
                    grant_amount=30000
                )
                
                # Отправляем сообщение с промокодом
                message = (
                    "🎉 <b>Поздравляем!</b>\n\n"
                    "Привет, мы видели твои классные способности, вот тебе грант на 30 тысяч на любую профессию школы Банбэнк Эдюкейшн.\n\n"
                    f"🎫 <b>Твой промокод:</b> <code>{promo_code}</code>\n\n"
                    "🔗 <a href='https://bangbangeducation.ru/sale'>Bang Bang Education</a>"
                )
                
                await bot.send_message(
                    chat_id=leader_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                
                granted_count += 1
                logger.info(f"Грант с промокодом {promo_code} отправлен пользователю {leader_id} ({leader.get('username', leader.get('first_name', 'Unknown'))})")
                
                # Небольшая задержка между отправками
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Ошибка при выдаче гранта пользователю {leader.get('user_id')}: {e}", exc_info=True)
        
        logger.info(f"Выдано {granted_count} грантов из {len(eligible_leaders)} подходящих лидеров")
        
    except Exception as e:
        logger.error(f"Ошибка при выдаче грантов: {e}", exc_info=True)


async def send_riddles_to_users(context: ContextTypes.DEFAULT_TYPE):
    """Отправлять напоминания о загадках неактивным пользователям каждые 3 часа"""
    try:
        # Получаем только пользователей с активными загадками (неактивные)
        users = await database.get_users_with_active_riddles()
        if not users:
            logger.info("Нет пользователей с активными загадками для напоминания")
            return
        
        bot = context.bot
        sent_count = 0
        
        for user_id in users:
            try:
                # Получаем активную загадку пользователя
                riddle_id = await database.get_user_active_riddle_id(user_id)
                if not riddle_id:
                    continue
                
                # Получаем информацию о загадке
                riddle = await database.get_riddle_by_id(riddle_id)
                if not riddle:
                    continue
                
                message = (
                    f"⏰ <b>Напоминание!</b>\n\n"
                    f"🎨 <b>Дизайнерская загадка:</b>\n{riddle['question']}\n\n"
                    f"Отправьте свой ответ сообщением!"
                )
                
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='HTML'
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")
        
        logger.info(f"Отправлено {sent_count} напоминаний пользователям")
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминаний: {e}")


async def send_riddle_to_user(user_id: int, bot, active_riddle=None, is_new=True):
    """Отправить загадку конкретному пользователю"""
    try:
        if not active_riddle:
            if is_new:
                # Если is_new=True, ВСЕГДА создаем новую загадку
                logger.info(f"[НОВАЯ ЗАГАДКА] Генерация новой загадки для пользователя {user_id}")
                
                # Генерируем новую загадку, проверяя что она уникальна для пользователя
                max_attempts = 10  # Максимум попыток найти уникальную загадку
                riddle = None
                riddle_id = None
                
                for attempt in range(max_attempts):
                    # Получаем случайную загадку
                    riddle = riddle_generator.get_random_riddle()
                    
                    # Проверяем, не видел ли пользователь эту загадку
                    user_saw_this = await database.user_has_seen_riddle(user_id, riddle["question"])
                    
                    if not user_saw_this:
                        # Проверяем, не добавлена ли уже эта загадка в базу
                        existing_riddle = await database.get_riddle_by_question(riddle["question"])
                        
                        if existing_riddle:
                            # Загадка уже в базе, используем её если пользователь её не видел
                            riddle_id = existing_riddle["id"]
                            active_riddle = {
                                "id": riddle_id,
                                "question": existing_riddle["question"],
                                "answer": existing_riddle["answer"],
                                "hint": existing_riddle.get("hint")
                            }
                            logger.info(f"Используем существующую загадку #{riddle_id} для пользователя {user_id}")
                            break
                        else:
                            # Загадки нет в базе, добавляем новую
                            riddle_id = await database.add_riddle(
                                question=riddle["question"],
                                answer=riddle["answer"],
                                hint=riddle.get("hint")
                            )
                            if not riddle_id:
                                raise Exception("Не удалось создать загадку в базе данных")
                            
                            active_riddle = {
                                "id": riddle_id,
                                "question": riddle["question"],
                                "answer": riddle["answer"],
                                "hint": riddle.get("hint")
                            }
                            logger.info(f"Создана новая загадка #{riddle_id} для пользователя {user_id}")
                            break
                    else:
                        logger.info(f"Попытка {attempt + 1}: пользователь {user_id} уже видел эту загадку, пробуем другую")
                
                if not active_riddle:
                    # Если не удалось найти уникальную загадку, создаем любую новую
                    logger.warning(f"Не удалось найти уникальную загадку для {user_id}, создаем любую новую")
                    riddle = riddle_generator.get_random_riddle()
                    riddle_id = await database.add_riddle(
                        question=riddle["question"],
                        answer=riddle["answer"],
                        hint=riddle.get("hint")
                    )
                    if not riddle_id:
                        raise Exception("Не удалось создать загадку в базе данных")
                    
                    active_riddle = {
                        "id": riddle_id,
                        "question": riddle["question"],
                        "answer": riddle["answer"],
                        "hint": riddle.get("hint")
                    }
            else:
                # Если is_new=False, пытаемся найти нерешенную загадку
                logger.info(f"Поиск нерешенной загадки для пользователя {user_id}")
                active_riddle = await database.get_unsolved_riddle_for_user(user_id)
                
                # Если нерешенных загадок нет, создаем новую
                if not active_riddle:
                    logger.info(f"Нет нерешенных загадок, создаем новую для пользователя {user_id}")
                    riddle = riddle_generator.get_random_riddle()
                    riddle_id = await database.add_riddle(
                        question=riddle["question"],
                        answer=riddle["answer"],
                        hint=riddle.get("hint")
                    )
                    if not riddle_id:
                        raise Exception("Не удалось создать загадку в базе данных")
                    
                    active_riddle = {
                        "id": riddle_id,
                        "question": riddle["question"],
                        "answer": riddle["answer"],
                        "hint": riddle.get("hint")
                    }
                    logger.info(f"Создана новая загадка #{riddle_id} для пользователя {user_id}")
                else:
                    logger.info(f"Найдена нерешенная загадка #{active_riddle['id']} для пользователя {user_id}")
        
        # Установить активную загадку для пользователя
        await database.set_user_active_riddle(user_id, active_riddle['id'])
        logger.info(f"Установлена активная загадка #{active_riddle['id']} для пользователя {user_id}")
        
        if is_new:
            message = f"🎨 <b>Новая дизайнерская загадка!</b>\n\n{active_riddle['question']}\n\nОтправьте свой ответ сообщением!"
        else:
            message = f"🎨 <b>Дизайнерская загадка!</b>\n\n{active_riddle['question']}\n\nОтправьте свой ответ сообщением!"
        
        # Создаем клавиатуру с кнопками
        keyboard = [
            [
                InlineKeyboardButton("💡 Подсказка", callback_data=f"hint_{user_id}"),
                InlineKeyboardButton("📊 Статистика", callback_data=f"stats_{user_id}")
            ],
            [
                InlineKeyboardButton("🏆 Лидерборд", callback_data=f"leaderboard_{user_id}"),
                InlineKeyboardButton("🎲 Новая загадка", callback_data=f"new_riddle_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await bot.send_message(chat_id=user_id, text=message, parse_mode='HTML', reply_markup=reply_markup)
        logger.info(f"Загадка отправлена пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка в send_riddle_to_user для пользователя {user_id}: {e}", exc_info=True)
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        
        # Убеждаемся, что БД инициализирована
        try:
            await database.init_db()
        except Exception as e:
            logger.warning(f"БД уже инициализирована или ошибка: {e}")
        
        await database.get_or_create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        welcome_message = (
            f"👋 Привет, {user.first_name}!\n\n"
            "🎨 Я бот с дизайнерскими загадками!\n\n"
            "📝 <b>Как это работает:</b>\n"
            "• После правильного ответа сразу приходит новая загадка\n"
            "• Если не отвечаете, напоминание придет через 3 часа\n"
            "• Отправьте ответ обычным сообщением\n"
            "• Если ошибетесь 3 раза - получите подсказку\n"
            "• За правильные ответы получаете рейтинг!\n\n"
            "📊 <b>Используйте кнопки ниже для навигации!</b>\n\n"
            "Удачи! 🚀"
        )
        
        # Создаем постоянную клавиатуру с основными командами
        main_keyboard = [
            [KeyboardButton("🎲 Новая загадка"), KeyboardButton("📊 Моя статистика")],
            [KeyboardButton("🏆 Лидерборд"), KeyboardButton("💡 Подсказка")]
        ]
        reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
        await update.message.reply_text(welcome_message, parse_mode='HTML', reply_markup=reply_markup)
        
        # Сразу отправляем загадку
        try:
            await send_riddle_to_user(user.id, context.bot)
        except Exception as e:
            logger.error(f"Ошибка при отправке загадки пользователю {user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                "Произошла ошибка при отправке загадки. Попробуйте /riddle\n"
                f"Ошибка: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Критическая ошибка в start: {e}", exc_info=True)
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику пользователя"""
    user = update.effective_user if update.message else update.callback_query.from_user
    user_id = user.id
    stats_data = await database.get_user_stats(user_id)
    
    if not stats_data:
        message = "Статистика не найдена. Используйте /start"
    else:
        message = (
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"✅ Решено загадок: {stats_data['total_riddles_solved']}\n"
            f"📝 Попыток всего: {stats_data['total_riddles_attempted']}\n"
            f"💡 Подсказок использовано: {stats_data['total_hints_used']}\n"
            f"⭐ Рейтинг: {stats_data['rating']}\n"
        )
        
        if stats_data['total_riddles_attempted'] > 0:
            success_rate = (stats_data['total_riddles_solved'] / stats_data['total_riddles_attempted']) * 100
            message += f"📈 Процент успеха: {success_rate:.1f}%"
    
    if update.message:
        await update.message.reply_text(message, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.message.reply_text(message, parse_mode='HTML')


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать таблицу лидеров"""
    leaders = await database.get_leaderboard(limit=10)
    
    if not leaders:
        message = "Пока нет участников в рейтинге"
    else:
        message = "🏆 <b>Таблица лидеров:</b>\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, leader in enumerate(leaders, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            name = leader['username'] or leader['first_name'] or f"User {leader['user_id']}"
            message += (
                f"{medal} <b>{name}</b>\n"
                f"   ⭐ Рейтинг: {leader['rating']} | "
                f"✅ Решено: {leader['total_riddles_solved']}\n\n"
            )
    
    if update.message:
        await update.message.reply_text(message, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.message.reply_text(message, parse_mode='HTML')


async def riddle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить текущую загадку"""
    user = update.effective_user if update.message else update.callback_query.from_user
    user_id = user.id
    await database.get_or_create_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name
    )
    
    try:
        await send_riddle_to_user(user_id, context.bot, active_riddle=None, is_new=True)
    except Exception as e:
        logger.error(f"Ошибка при отправке загадки: {e}")
        error_msg = "Произошла ошибка. Попробуйте позже."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.message.reply_text(error_msg)


async def hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить подсказку"""
    user = update.effective_user if update.message else update.callback_query.from_user
    user_id = user.id
    hint_text = await database.get_hint(user_id)
    
    if not hint_text:
        # Получим информацию об активной загадке
        riddle_info = await database.get_user_active_riddle_info(user_id)
        if not riddle_info:
            message = "У вас нет активной загадки. Используйте /riddle чтобы получить загадку"
        else:
            wrong_attempts = riddle_info["wrong_attempts"]
            hints_given = riddle_info["hints_given"]
            needed = (hints_given + 1) * 3
            remaining = needed - wrong_attempts
            message = (
                f"❌ Недостаточно ошибок для подсказки!\n"
                f"Нужно еще {remaining} неправильных попыток (всего {needed} для следующей подсказки)"
            )
    else:
        message = f"💡 <b>Подсказка:</b> {hint_text}"
    
    # Отправляем сообщение (работает и для обычных сообщений, и для callback)
    if update.message:
        await update.message.reply_text(message, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(message, parse_mode='HTML')


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов от inline кнопок"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Регистрируем пользователя, если его нет
    await database.get_or_create_user(
        user_id=user_id,
        username=query.from_user.username,
        first_name=query.from_user.first_name
    )
    
    try:
        if data.startswith("hint_"):
            hint_text = await database.get_hint(user_id)
            if not hint_text:
                riddle_info = await database.get_user_active_riddle_info(user_id)
                if not riddle_info:
                    message = "У вас нет активной загадки. Используйте /riddle чтобы получить загадку"
                else:
                    wrong_attempts = riddle_info["wrong_attempts"]
                    hints_given = riddle_info["hints_given"]
                    needed = (hints_given + 1) * 3
                    remaining = needed - wrong_attempts
                    message = (
                        f"❌ Недостаточно ошибок для подсказки!\n"
                        f"Нужно еще {remaining} неправильных попыток (всего {needed} для следующей подсказки)"
                    )
            else:
                message = f"💡 <b>Подсказка:</b> {hint_text}"
            await query.message.reply_text(message, parse_mode='HTML')
            
        elif data.startswith("stats_"):
            stats_data = await database.get_user_stats(user_id)
            if not stats_data:
                message = "Статистика не найдена. Используйте /start"
            else:
                message = (
                    f"📊 <b>Ваша статистика:</b>\n\n"
                    f"✅ Решено загадок: {stats_data['total_riddles_solved']}\n"
                    f"📝 Попыток всего: {stats_data['total_riddles_attempted']}\n"
                    f"💡 Подсказок использовано: {stats_data['total_hints_used']}\n"
                    f"⭐ Рейтинг: {stats_data['rating']}\n"
                )
                if stats_data['total_riddles_attempted'] > 0:
                    success_rate = (stats_data['total_riddles_solved'] / stats_data['total_riddles_attempted']) * 100
                    message += f"📈 Процент успеха: {success_rate:.1f}%"
            await query.message.reply_text(message, parse_mode='HTML')
            
        elif data.startswith("leaderboard_"):
            leaders = await database.get_leaderboard(limit=10)
            if not leaders:
                message = "Пока нет участников в рейтинге"
            else:
                message = "🏆 <b>Таблица лидеров:</b>\n\n"
                medals = ["🥇", "🥈", "🥉"]
                for i, leader in enumerate(leaders, 1):
                    medal = medals[i-1] if i <= 3 else f"{i}."
                    name = leader['username'] or leader['first_name'] or f"User {leader['user_id']}"
                    message += (
                        f"{medal} <b>{name}</b>\n"
                        f"   ⭐ Рейтинг: {leader['rating']} | "
                        f"✅ Решено: {leader['total_riddles_solved']}\n\n"
                    )
            await query.message.reply_text(message, parse_mode='HTML')
            
        elif data.startswith("new_riddle_"):
            # Отправляем новую загадку
            await send_riddle_to_user(user_id, context.bot, active_riddle=None, is_new=True)
            
    except Exception as e:
        logger.error(f"Ошибка в handle_callback: {e}", exc_info=True)
        await query.message.reply_text("Произошла ошибка. Попробуйте позже.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (ответы на загадки и кнопки)"""
    user = update.effective_user
    user_answer = update.message.text.strip()
    
    # Игнорируем команды
    if user_answer.startswith('/'):
        return
    
    # Обработка кнопок ReplyKeyboard
    if user_answer == "🎲 Новая загадка":
        await riddle(update, context)
        return
    elif user_answer == "📊 Моя статистика":
        await stats(update, context)
        return
    elif user_answer == "🏆 Лидерборд":
        await leaderboard(update, context)
        return
    elif user_answer == "💡 Подсказка":
        await hint(update, context)
        return
    
    # Регистрируем пользователя, если его нет
    await database.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    # Проверяем ответ
    result = await database.check_answer(user.id, user_answer)
    
    if "error" in result:
        # Если нет активной загадки, отправляем новую
        await update.message.reply_text(
            "❌ У вас сейчас нет активной загадки.\n"
            "Отправляю новую загадку..."
        )
        try:
            await send_riddle_to_user(user.id, context.bot, active_riddle=None, is_new=True)
        except Exception as e:
            logger.error(f"Ошибка при отправке загадки: {e}")
            await update.message.reply_text("Используйте /riddle чтобы получить загадку")
        return
    
    # ПРАВИЛЬНЫЙ ОТВЕТ - полностью переписанная логика
    if result["is_correct"]:
        hints_given = result.get("hints_given", 0)
        
        # Проверяем, решена ли загадка повторно
        if result.get("already_solved", False):
            # Повторный правильный ответ на уже решенную загадку
            message = "✅ Ты уже ответил на эту загадку!\n\nСейчас пришлю следующую загадку, пидар 😏"
        else:
            # Первое правильное решение - ТОЛЬКО сообщение о правильности и баллах
            # НЕ показываем номер попытки вообще!
            message = "✅ <b>Правильно!</b> 🎉\n\nВы получили +10 к рейтингу!"
            
            # Если была подсказка, отмечаем это
            if hints_given > 0:
                message += "\n\nОтлично, что справились даже с подсказкой! 🎯"
        
        # Отправляем сообщение о правильном ответе
        await update.message.reply_text(message, parse_mode='HTML')
        
        # СРАЗУ отправляем НОВУЮ загадку (всегда генерируем новую уникальную)
        try:
            logger.info(f"[ПРАВИЛЬНЫЙ ОТВЕТ] Генерация и отправка новой уникальной загадки пользователю {user.id}")
            
            # Используем send_riddle_to_user с is_new=True - она сама найдет уникальную загадку
            await send_riddle_to_user(user.id, context.bot, active_riddle=None, is_new=True)
            logger.info(f"[УСПЕХ] Новая уникальная загадка отправлена пользователю {user.id}")
        except Exception as e:
            logger.error(f"[ОШИБКА] Не удалось отправить новую загадку пользователю {user.id}: {e}", exc_info=True)
            try:
                await update.message.reply_text("Произошла ошибка. Используйте /riddle для новой загадки")
            except:
                pass
    
    # НЕПРАВИЛЬНЫЙ ОТВЕТ
    else:
        wrong_attempts = result["wrong_attempts"]
        hints_given = result["hints_given"]
        attempt_number = result.get("attempt_number", 0)
        
        # Получаем статистику пользователя для проверки рекомендаций
        user_stats = await database.get_user_stats(user.id)
        total_hints_used = user_stats["total_hints_used"] if user_stats else 0
        
        message = f"❌ Неправильно! Попытка #{attempt_number}\n📉 Вы потеряли 5 баллов рейтинга"
        
        # Вычисляем ошибки после подсказки
        wrong_attempts_after_hint = wrong_attempts - (hints_given * 3)
        
        # Получаем информацию о текущей загадке для рекомендации курса
        current_riddle = None
        try:
            riddle_info = await database.get_user_active_riddle_info(user.id)
            if riddle_info:
                current_riddle = await database.get_riddle_by_id(riddle_info["riddle_id"])
        except Exception as e:
            logger.error(f"Ошибка при получении информации о загадке: {e}")
        
        # Проверяем, нужно ли дать подсказку (первая подсказка после 3 ошибок)
        if hints_given == 0 and wrong_attempts >= 3:
            hint_text = await database.get_hint(user.id)
            if hint_text:
                message += f"\n\n💡 <b>Подсказка:</b> {hint_text}"
        # Если подсказка уже была дана, показываем сколько ошибок после подсказки
        elif hints_given > 0:
            remaining_after_hint = 3 - wrong_attempts_after_hint
            if remaining_after_hint > 0:
                message += f"\n\nПосле подсказки осталось {remaining_after_hint} попыток"
            # Если после подсказки 3 ошибки - показываем ответ и отправляем новую загадку
            elif wrong_attempts_after_hint >= 3:
                # Получаем правильный ответ из активной загадки
                if current_riddle:
                    message += f"\n\n❌ Правильный ответ: <b>{current_riddle['answer']}</b>"
        else:
            # До подсказки еще не дошли
            remaining = 3 - wrong_attempts
            message += f"\n\nОсталось {remaining} ошибок до подсказки"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
        # Рекомендация курса: если 3 попытки использованы ИЛИ использовано 5-10 подсказок
        # НО только один раз в день!
        should_recommend_course = False
        if attempt_number == 3:  # Использовано 3 попытки
            should_recommend_course = True
        elif 5 <= total_hints_used <= 10:  # Использовано 5-10 подсказок
            should_recommend_course = True
        
        if should_recommend_course and current_riddle:
            # Проверяем, отправляли ли уже рекомендацию сегодня
            can_send = await database.should_send_course_recommendation(user.id)
            
            if can_send:
                try:
                    # Определяем курс по теме загадки
                    course = course_recommendations.get_course_by_riddle_theme(
                        current_riddle["question"],
                        current_riddle["answer"]
                    )
                    course_message = course_recommendations.format_course_recommendation(course)
                    
                    # Небольшая задержка перед рекомендацией
                    await asyncio.sleep(1)
                    await update.message.reply_text(course_message, parse_mode='HTML', disable_web_page_preview=False)
                    
                    # Отмечаем, что рекомендация отправлена сегодня
                    await database.mark_course_recommendation_sent(user.id)
                    logger.info(f"Рекомендация курса отправлена пользователю {user.id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке рекомендации курса: {e}", exc_info=True)
            else:
                logger.info(f"Рекомендация курса уже была отправлена пользователю {user.id} сегодня, пропускаем")
        
        # Если после подсказки было 3 ошибки - отправляем новую загадку
        if hints_given > 0 and wrong_attempts_after_hint >= 3:
            # Удаляем текущую активную загадку
            try:
                await database.clear_user_active_riddle(user.id)
                logger.info(f"Удалена активная загадка для пользователя {user.id} после 3 ошибок после подсказки")
            except Exception as e:
                logger.error(f"Ошибка при удалении активной загадки: {e}")
            
            # Небольшая задержка, затем отправляем новую загадку
            await asyncio.sleep(0.5)
            
            try:
                logger.info(f"[3 ОШИБКИ ПОСЛЕ ПОДСКАЗКИ] Отправка новой уникальной загадки пользователю {user.id}")
                await send_riddle_to_user(user.id, context.bot, active_riddle=None, is_new=True)
                logger.info(f"[УСПЕХ] Новая уникальная загадка отправлена пользователю {user.id}")
            except Exception as e:
                logger.error(f"[ОШИБКА] Не удалось отправить новую загадку пользователю {user.id}: {e}", exc_info=True)
                try:
                    await update.message.reply_text("Используйте /riddle для новой загадки")
                except:
                    pass


async def post_init(app: Application):
    """Инициализация после запуска бота"""
    # Инициализация БД
    await database.init_db()
    logger.info("База данных инициализирована")
    
    # Генерируем начальный набор загадок
    await generate_daily_riddles()
    
    # Настраиваем планировщик
    # Генерация загадок каждый день в полночь
    scheduler.add_job(
        generate_daily_riddles,
        trigger=CronTrigger(hour=0, minute=0),
        id='generate_daily_riddles',
        replace_existing=True
    )
    
    # Обновление рейтинга каждую неделю в понедельник в 00:00
    scheduler.add_job(
        update_weekly_ratings,
        trigger=CronTrigger(day_of_week='mon', hour=0, minute=0),
        id='update_weekly_ratings',
        replace_existing=True
    )
    
    # Выдача грантов топ-10 лидерам каждое воскресенье
    scheduler.add_job(
        weekly_grant_raffle,
        trigger=CronTrigger(day_of_week='sun', hour=0, minute=0),
        args=[app],
        id='weekly_grant_distribution',
        replace_existing=True
    )
    
    # Отправка напоминаний неактивным пользователям каждые 3 часа
    scheduler.add_job(
        send_riddles_to_users,
        trigger=IntervalTrigger(hours=3),
        args=[app],
        id='send_reminders',
        replace_existing=True
    )
    
    scheduler.start()
    scheduler.start()
    logger.info("=" * 60)
    logger.info("✅ ПЛАНИРОВЩИК ЗАПУЩЕН")
    logger.info("=" * 60)
    logger.info("📅 Генерация загадок: каждый день в 00:00 (20 загадок)")
    logger.info("🔄 Очистка турнирной таблицы: каждый понедельник в 00:00 (сброс рейтинга до 1000)")
    logger.info("🎁 Выдача грантов: каждое воскресенье в 00:00 (топ-10 лидеров, 30 000₽, промокоды)")
    logger.info("⏰ Напоминания о загадках: каждые 3 часа (только неактивным пользователям)")
    logger.info("✨ Новые загадки отправляются сразу после правильного ответа")
    logger.info("=" * 60)


def main():
    """Главная функция запуска бота"""
    # Создаем приложение
    application = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("riddle", riddle))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("hint", hint))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

