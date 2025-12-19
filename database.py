import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
import answer_checker

DB_PATH = "riddle_bot.db"


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица загадок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS riddles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                hint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                total_riddles_solved INTEGER DEFAULT 0,
                total_riddles_attempted INTEGER DEFAULT 0,
                total_hints_used INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 1000,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица попыток ответов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                riddle_id INTEGER,
                answer TEXT,
                is_correct BOOLEAN,
                attempt_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (riddle_id) REFERENCES riddles(id)
            )
        """)
        
        # Таблица текущих активных загадок для пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_active_riddles (
                user_id INTEGER,
                riddle_id INTEGER,
                wrong_attempts INTEGER DEFAULT 0,
                hints_given INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, riddle_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (riddle_id) REFERENCES riddles(id)
            )
        """)
        
        # Таблица истории грантов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS grants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                grant_amount INTEGER DEFAULT 30000,
                promo_code TEXT UNIQUE,
                week_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        await db.commit()


async def add_riddle(question: str, answer: str, hint: str = None):
    """Добавить новую загадку"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO riddles (question, answer, hint) VALUES (?, ?, ?)",
            (question, answer, hint)
        )
        await db.commit()
        cursor = await db.execute("SELECT last_insert_rowid()")
        result = await cursor.fetchone()
        return result[0] if result else None


async def get_active_riddle():
    """Получить текущую активную загадку"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, question, answer, hint FROM riddles WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1"
        )
        result = await cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "question": result[1],
                "answer": result[2],
                "hint": result[3]
            }
        return None


async def get_riddle_by_id(riddle_id: int) -> Optional[Dict]:
    """Получить загадку по ID"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, question, answer, hint FROM riddles WHERE id = ?",
            (riddle_id,)
        )
        result = await cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "question": result[1],
                "answer": result[2],
                "hint": result[3]
            }
        return None


async def get_unsolved_riddle_for_user(user_id: int) -> Optional[Dict]:
    """Получить нерешенную загадку для пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем все загадки, которые пользователь еще не решил
        cursor = await db.execute(
            """SELECT r.id, r.question, r.answer, r.hint
               FROM riddles r
               WHERE r.is_active = 1
               AND r.id NOT IN (
                   SELECT DISTINCT riddle_id 
                   FROM attempts 
                   WHERE user_id = ? AND is_correct = 1
               )
               ORDER BY r.created_at DESC
               LIMIT 1""",
            (user_id,)
        )
        result = await cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "question": result[1],
                "answer": result[2],
                "hint": result[3]
            }
        return None


async def get_or_create_user(user_id: int, username: str = None, first_name: str = None):
    """Получить или создать пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        user = await cursor.fetchone()
        
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            await db.commit()
            return {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "total_riddles_solved": 0,
                "total_riddles_attempted": 0,
                "total_hints_used": 0,
                "rating": 1000
            }
        
        return {
            "user_id": user[0],
            "username": user[1],
            "first_name": user[2],
            "total_riddles_solved": user[3],
            "total_riddles_attempted": user[4],
            "total_hints_used": user[5],
            "rating": user[6]
        }


async def set_user_active_riddle(user_id: int, riddle_id: int):
    """Установить активную загадку для пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO user_active_riddles 
               (user_id, riddle_id, wrong_attempts, hints_given) 
               VALUES (?, ?, 0, 0)""",
            (user_id, riddle_id)
        )
        await db.commit()


async def check_answer(user_id: int, answer: str) -> Dict:
    """Проверить ответ пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Получить активную загадку пользователя
        cursor = await db.execute(
            """SELECT uar.riddle_id, uar.wrong_attempts, uar.hints_given, 
                      r.answer, r.id
               FROM user_active_riddles uar
               JOIN riddles r ON uar.riddle_id = r.id
               WHERE uar.user_id = ?""",
            (user_id,)
        )
        result = await cursor.fetchone()
        
        if not result:
            return {"error": "Нет активной загадки"}
        
        riddle_id, wrong_attempts, hints_given, correct_answer, riddle_db_id = result
        
        # Проверяем, решена ли уже эта загадка пользователем
        cursor = await db.execute(
            "SELECT COUNT(*) FROM attempts WHERE user_id = ? AND riddle_id = ? AND is_correct = 1",
            (user_id, riddle_db_id)
        )
        already_solved = (await cursor.fetchone())[0] > 0
        
        # Гибкая проверка ответа с учетом морфологии
        is_correct = answer_checker.check_answer_flexible(answer, correct_answer)
        
        # Получить номер попытки
        cursor = await db.execute(
            "SELECT COUNT(*) FROM attempts WHERE user_id = ? AND riddle_id = ?",
            (user_id, riddle_db_id)
        )
        attempt_count = (await cursor.fetchone())[0]
        attempt_number = attempt_count + 1
        
        # Сохранить попытку
        await db.execute(
            "INSERT INTO attempts (user_id, riddle_id, answer, is_correct, attempt_number) VALUES (?, ?, ?, ?, ?)",
            (user_id, riddle_db_id, answer, is_correct, attempt_number)
        )
        
        if is_correct:
            # Если загадка уже была решена, не даем баллы
            if not already_solved:
                # Обновить статистику пользователя только если это первое правильное решение
                await db.execute(
                    """UPDATE users 
                       SET total_riddles_solved = total_riddles_solved + 1,
                           total_riddles_attempted = total_riddles_attempted + 1,
                           rating = rating + 10
                       WHERE user_id = ?""",
                    (user_id,)
                )
            else:
                # Если уже решена, только обновляем счетчик попыток (без баллов)
                await db.execute(
                    "UPDATE users SET total_riddles_attempted = total_riddles_attempted + 1 WHERE user_id = ?",
                    (user_id,)
                )
            
            # Удалить активную загадку
            await db.execute(
                "DELETE FROM user_active_riddles WHERE user_id = ? AND riddle_id = ?",
                (user_id, riddle_id)
            )
        else:
            # Увеличить счетчик неправильных попыток
            new_wrong_attempts = wrong_attempts + 1
            await db.execute(
                "UPDATE user_active_riddles SET wrong_attempts = ? WHERE user_id = ? AND riddle_id = ?",
                (new_wrong_attempts, user_id, riddle_id)
            )
            # Обновить статистику попыток и уменьшить рейтинг на 5 баллов
            await db.execute(
                """UPDATE users 
                   SET total_riddles_attempted = total_riddles_attempted + 1,
                       rating = MAX(0, rating - 5)
                   WHERE user_id = ?""",
                (user_id,)
            )
        
        await db.commit()
        
        # Возвращаем результат БЕЗ номера попытки для правильных ответов
        result_dict = {
            "is_correct": is_correct,
            "wrong_attempts": wrong_attempts + (0 if is_correct else 1),
            "hints_given": hints_given,
            "already_solved": already_solved if is_correct else False
        }
        
        # Номер попытки только для неправильных ответов
        if not is_correct:
            result_dict["attempt_number"] = attempt_number
        
        return result_dict


async def get_user_active_riddle_info(user_id: int) -> Optional[Dict]:
    """Получить информацию об активной загадке пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT uar.riddle_id, uar.wrong_attempts, uar.hints_given
               FROM user_active_riddles uar
               WHERE uar.user_id = ?""",
            (user_id,)
        )
        result = await cursor.fetchone()
        
        if not result:
            return None
        
        return {
            "riddle_id": result[0],
            "wrong_attempts": result[1],
            "hints_given": result[2]
        }


async def get_hint(user_id: int) -> Optional[str]:
    """Получить подсказку для пользователя (если есть 3+ ошибки)"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT uar.riddle_id, uar.wrong_attempts, uar.hints_given, r.hint
               FROM user_active_riddles uar
               JOIN riddles r ON uar.riddle_id = r.id
               WHERE uar.user_id = ?""",
            (user_id,)
        )
        result = await cursor.fetchone()
        
        if not result:
            return None
        
        riddle_id, wrong_attempts, hints_given, hint = result
        
        # Проверяем, нужно ли дать подсказку (каждые 3 ошибки)
        if wrong_attempts >= (hints_given + 1) * 3 and hint:
            new_hints_given = hints_given + 1
            await db.execute(
                "UPDATE user_active_riddles SET hints_given = ? WHERE user_id = ? AND riddle_id = ?",
                (new_hints_given, user_id, riddle_id)
            )
            await db.execute(
                "UPDATE users SET total_hints_used = total_hints_used + 1 WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
            return hint
        
        return None


async def get_leaderboard(limit: int = 10) -> List[Dict]:
    """Получить таблицу лидеров"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT user_id, username, first_name, rating, total_riddles_solved
               FROM users
               ORDER BY rating DESC, total_riddles_solved DESC
               LIMIT ?""",
            (limit,)
        )
        results = await cursor.fetchall()
        return [
            {
                "user_id": row[0],
                "username": row[1],
                "first_name": row[2],
                "rating": row[3],
                "total_riddles_solved": row[4]
            }
            for row in results
        ]


async def get_user_stats(user_id: int) -> Optional[Dict]:
    """Получить статистику пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        result = await cursor.fetchone()
        if result:
            return {
                "user_id": result[0],
                "username": result[1],
                "first_name": result[2],
                "total_riddles_solved": result[3],
                "total_riddles_attempted": result[4],
                "total_hints_used": result[5],
                "rating": result[6]
            }
        return None


async def get_all_users():
    """Получить всех пользователей"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        results = await cursor.fetchall()
        return [row[0] for row in results]


async def get_users_with_active_riddles():
    """Получить пользователей с активными загадками"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT DISTINCT user_id FROM user_active_riddles")
        results = await cursor.fetchall()
        return [row[0] for row in results]


async def get_user_active_riddle_id(user_id: int) -> Optional[int]:
    """Получить ID активной загадки пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT riddle_id FROM user_active_riddles WHERE user_id = ?",
            (user_id,)
        )
        result = await cursor.fetchone()
        return result[0] if result else None


async def clear_user_active_riddle(user_id: int):
    """Удалить активную загадку пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM user_active_riddles WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def reset_weekly_ratings():
    """Обновить рейтинг каждую неделю (можно сбросить или пересчитать)"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Вариант 1: Сброс рейтинга до базового значения
        # await db.execute("UPDATE users SET rating = 1000")
        
        # Вариант 2: Пересчет рейтинга на основе решенных загадок
        # Рейтинг = базовый (1000) + (решенные загадки * 10) - (использованные подсказки * 5)
        await db.execute("""
            UPDATE users 
            SET rating = 1000 + (total_riddles_solved * 10) - (total_hints_used * 5)
            WHERE rating < 0 OR rating IS NULL
        """)
        
        # Обновляем рейтинг для всех пользователей на основе их активности
        await db.execute("""
            UPDATE users 
            SET rating = 1000 + (total_riddles_solved * 10) - (total_hints_used * 5)
        """)
        
        await db.commit()
        logger.info("Рейтинг обновлен для всех пользователей")


async def get_weekly_leaderboard(limit: int = 10) -> List[Dict]:
    """Получить лидеров недели для розыгрыша"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT user_id, username, first_name, rating, total_riddles_solved
               FROM users
               WHERE rating > 0
               ORDER BY rating DESC, total_riddles_solved DESC
               LIMIT ?""",
            (limit,)
        )
        results = await cursor.fetchall()
        return [
            {
                "user_id": row[0],
                "username": row[1],
                "first_name": row[2],
                "rating": row[3],
                "total_riddles_solved": row[4]
            }
            for row in results
        ]


async def save_grant_winner(user_id: int, promo_code: str, grant_amount: int = 30000, week_date: str = None):
    """Сохранить победителя гранта с промокодом"""
    async with aiosqlite.connect(DB_PATH) as db:
        if not week_date:
            from datetime import datetime
            week_date = datetime.now().strftime("%Y-%m-%d")
        
        await db.execute(
            "INSERT INTO grants (user_id, grant_amount, promo_code, week_date) VALUES (?, ?, ?, ?)",
            (user_id, grant_amount, promo_code, week_date)
        )
        await db.commit()


async def get_all_promo_codes() -> List[str]:
    """Получить все существующие промокоды"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT promo_code FROM grants WHERE promo_code IS NOT NULL")
        results = await cursor.fetchall()
        return [row[0] for row in results if row[0]]


async def has_received_grant_this_week(user_id: int) -> bool:
    """Проверить, получал ли пользователь грант на этой неделе"""
    async with aiosqlite.connect(DB_PATH) as db:
        from datetime import datetime, timedelta
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        
        cursor = await db.execute(
            "SELECT COUNT(*) FROM grants WHERE user_id = ? AND week_date >= ?",
            (user_id, week_start)
        )
        count = (await cursor.fetchone())[0]
        return count > 0


async def has_ever_received_grant(user_id: int) -> bool:
    """Проверить, получал ли пользователь грант когда-либо"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM grants WHERE user_id = ?",
            (user_id,)
        )
        count = (await cursor.fetchone())[0]
        return count > 0

