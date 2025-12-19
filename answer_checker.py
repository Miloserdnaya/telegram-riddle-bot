"""
Модуль для умной проверки ответов с учетом морфологии русского языка
"""
import re
try:
    import pymorphy3
    morph = pymorphy3.MorphAnalyzer()
    PYMORPHY_AVAILABLE = True
except ImportError:
    PYMORPHY_AVAILABLE = False
    morph = None


def normalize_text(text: str) -> str:
    """Нормализация текста: удаление лишних пробелов, знаков препинания"""
    if not text:
        return ""
    # Удаляем лишние пробелы и приводим к нижнему регистру
    text = re.sub(r'\s+', ' ', text.strip().lower())
    # Удаляем знаки препинания в конце (но оставляем внутри для составных ответов)
    text = text.rstrip('.,!?;:')
    # Удаляем лишние пробелы в начале и конце еще раз
    text = text.strip()
    return text


def get_normal_forms(text: str) -> set:
    """Получить нормальные формы всех слов в тексте"""
    if not PYMORPHY_AVAILABLE:
        # Если pymorphy3 не установлен, возвращаем просто нормализованный текст
        return {normalize_text(text)}
    
    words = re.findall(r'\b[а-яёa-z]+\b', text.lower())
    normal_forms = set()
    
    for word in words:
        if len(word) < 2:  # Пропускаем слишком короткие слова
            continue
        try:
            parsed = morph.parse(word)[0]
            normal_form = parsed.normal_form
            normal_forms.add(normal_form)
            # Также добавляем само слово на случай, если оно уже в нормальной форме
            normal_forms.add(word)
        except:
            # Если не удалось распарсить, добавляем как есть
            normal_forms.add(word)
    
    return normal_forms


def check_answer_flexible(user_answer: str, correct_answer: str) -> bool:
    """
    Гибкая проверка ответа с учетом морфологии и разных форм слов
    
    Проверяет:
    1. Точное совпадение (после нормализации)
    2. Совпадение нормальных форм всех слов
    3. Содержание ключевых слов из правильного ответа в ответе пользователя
    """
    if not user_answer or not correct_answer:
        return False
    
    # Очистка входных данных
    user_answer = str(user_answer).strip()
    correct_answer = str(correct_answer).strip()
    
    if not user_answer or not correct_answer:
        return False
    
    # Нормализация
    user_norm = normalize_text(user_answer)
    correct_norm = normalize_text(correct_answer)
    
    # 1. Точное совпадение после нормализации (самый простой случай)
    if user_norm == correct_norm:
        return True
    
    # 1.1. Для очень коротких ответов (1-2 слова) - строгая проверка
    if len(correct_norm.split()) <= 2 and len(user_norm.split()) <= 2:
        # Проверяем точное совпадение нормальных форм
        if user_norm == correct_norm:
            return True
    
    # 2. Получаем нормальные формы всех значимых слов
    user_forms = get_normal_forms(user_answer)
    correct_forms = get_normal_forms(correct_answer)
    
    # Если множества нормальных форм совпадают
    if user_forms and correct_forms:
        # Проверяем, содержатся ли все ключевые слова из правильного ответа
        matched_forms = user_forms.intersection(correct_forms)
        
        if len(correct_forms) > 0:
            match_ratio = len(matched_forms) / len(correct_forms)
            
            # Для коротких ответов (1-3 слова) требуем полное совпадение всех слов
            if len(correct_forms) <= 3:
                # Для односложных ответов (1 слово) - строгая проверка
                if len(correct_forms) == 1:
                    if len(matched_forms) >= 1:  # Хотя бы одна нормальная форма совпала
                        return True
                elif match_ratio >= 1.0:  # Все слова должны совпасть
                    return True
            else:
                # Для длинных ответов достаточно 80%+ совпадения
                if match_ratio >= 0.8:
                    return True
    
    # 3. Проверка на вхождение ключевых слов (более гибкая)
    # Извлекаем значимые слова (от 2 букв для коротких слов, от 3 для длинных)
    correct_words = re.findall(r'\b[а-яёa-z]{2,}\b', correct_norm)
    user_words = re.findall(r'\b[а-яёa-z]{2,}\b', user_norm)
    
    if correct_words:
        # Получаем нормальные формы для сравнения
        correct_normal_words = set()
        user_normal_words = set()
        
        for word in correct_words:
            if len(word) < 2:  # Пропускаем слишком короткие
                continue
            if PYMORPHY_AVAILABLE:
                try:
                    parsed = morph.parse(word)[0]
                    normal = parsed.normal_form
                    correct_normal_words.add(normal)
                    # Также добавляем само слово
                    correct_normal_words.add(word)
                except:
                    correct_normal_words.add(word)
            else:
                correct_normal_words.add(word)
        
        for word in user_words:
            if len(word) < 2:
                continue
            if PYMORPHY_AVAILABLE:
                try:
                    parsed = morph.parse(word)[0]
                    normal = parsed.normal_form
                    user_normal_words.add(normal)
                    user_normal_words.add(word)
                except:
                    user_normal_words.add(word)
            else:
                user_normal_words.add(word)
        
        # Если все ключевые слова из правильного ответа есть в ответе пользователя
        if correct_normal_words and user_normal_words:
            # Для коротких ответов (1-2 слова) требуем точное совпадение
            if len(correct_normal_words) <= 2:
                if correct_normal_words.issubset(user_normal_words):
                    return True
            else:
                # Для длинных ответов проверяем, что большинство ключевых слов присутствует
                matched = correct_normal_words.intersection(user_normal_words)
                if len(matched) >= len(correct_normal_words) * 0.7:  # 70% совпадение
                    return True
    
    # 4. Проверка на частичное совпадение для длинных ответов
    if len(correct_norm) > 10 and len(user_norm) > 5:
        # Проверяем, содержится ли правильный ответ в ответе пользователя (или наоборот)
        if correct_norm in user_norm or user_norm in correct_norm:
            return True
    
    # 5. Специальная обработка для ответов с числами и аббревиатурами
    # Извлекаем числа и аббревиатуры отдельно
    correct_numbers = re.findall(r'\d+[.,:]\d+|\d+', correct_norm)
    user_numbers = re.findall(r'\d+[.,:]\d+|\d+', user_norm)
    
    if correct_numbers:
        if set(correct_numbers) == set(user_numbers):
            # Если числа совпадают, проверяем остальные слова
            correct_text_only = re.sub(r'\d+[.,:]\d+|\d+', '', correct_norm).strip()
            user_text_only = re.sub(r'\d+[.,:]\d+|\d+', '', user_norm).strip()
            if correct_text_only and user_text_only:
                return check_answer_flexible(user_text_only, correct_text_only)
    
    # 6. Проверка аббревиатур (заглавные буквы)
    correct_abbr = re.findall(r'\b[А-ЯЁA-Z]{2,}\b', correct_answer)
    user_abbr = re.findall(r'\b[А-ЯЁA-Z]{2,}\b', user_answer)
    
    if correct_abbr:
        correct_abbr_lower = {abbr.lower() for abbr in correct_abbr}
        user_abbr_lower = {abbr.lower() for abbr in user_abbr}
        if correct_abbr_lower.issubset(user_abbr_lower):
            # Если аббревиатуры совпадают, проверяем остальной текст
            correct_without_abbr = correct_norm
            user_without_abbr = user_norm
            for abbr in correct_abbr:
                correct_without_abbr = correct_without_abbr.replace(abbr.lower(), '').strip()
            for abbr in user_abbr:
                user_without_abbr = user_without_abbr.replace(abbr.lower(), '').strip()
            
            if correct_without_abbr and user_without_abbr:
                # Рекурсивно проверяем остальной текст
                return check_answer_flexible(user_without_abbr, correct_without_abbr)
            elif not correct_without_abbr and not user_without_abbr:
                # Если только аббревиатуры - они уже совпали
                return True
    
    return False

