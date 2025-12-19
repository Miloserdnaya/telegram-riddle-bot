"""
Генератор уникальных промокодов для грантов
"""
import random
import string
from datetime import datetime


def generate_promo_code(prefix: str = "BBE") -> str:
    """
    Генерировать уникальный промокод
    Формат: BBE-XXXX-XXXX-XXXX (где X - буквы и цифры)
    """
    # Генерируем случайную часть из букв и цифр
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(12))
    
    # Форматируем как BBE-XXXX-XXXX-XXXX
    promo_code = f"{prefix}-{random_part[:4]}-{random_part[4:8]}-{random_part[8:12]}"
    
    return promo_code


def generate_unique_promo_code(existing_codes: list, prefix: str = "BBE") -> str:
    """Генерировать уникальный промокод, проверяя на дубликаты"""
    max_attempts = 100
    for _ in range(max_attempts):
        promo_code = generate_promo_code(prefix)
        if promo_code not in existing_codes:
            return promo_code
    # Если не удалось сгенерировать уникальный, добавляем timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp[:4]}-{timestamp[4:8]}-{timestamp[8:12]}"

