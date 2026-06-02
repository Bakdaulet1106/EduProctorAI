"""
EduProctorAI - Helper Functions
"""
import re
import hashlib
import random
import string
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


def validate_iin(iin: str) -> bool:
    if not iin or not isinstance(iin, str):
        return False
    iin = re.sub(r'[\s-]', '', iin)
    if len(iin) != 12 or not iin.isdigit():
        return False
    try:
        month = int(iin[2:4])
        day = int(iin[4:6])
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
    except ValueError:
        return False
    return True


def validate_email(email: str) -> bool:
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    if not phone:
        return False
    phone = re.sub(r'\D', '', phone)
    return len(phone) in [10, 11, 12] and (phone.startswith('7') or phone.startswith('8'))


def percentage_to_gpa(percentage: float) -> float:
    if percentage >= 95:
        return 4.0
    elif percentage >= 90:
        return 3.67
    elif percentage >= 85:
        return 3.33
    elif percentage >= 80:
        return 3.0
    elif percentage >= 75:
        return 2.67
    elif percentage >= 70:
        return 2.33
    elif percentage >= 65:
        return 2.0
    elif percentage >= 60:
        return 1.67
    elif percentage >= 55:
        return 1.33
    elif percentage >= 50:
        return 1.0
    elif percentage >= 25:
        return 0.5
    else:
        return 0.0


def get_letter_grade(percentage: float) -> str:
    if percentage >= 95:
        return "A"
    elif percentage >= 90:
        return "A-"
    elif percentage >= 85:
        return "B+"
    elif percentage >= 80:
        return "B"
    elif percentage >= 75:
        return "B-"
    elif percentage >= 70:
        return "C+"
    elif percentage >= 65:
        return "C"
    elif percentage >= 60:
        return "C-"
    elif percentage >= 55:
        return "D+"
    elif percentage >= 50:
        return "D"
    elif percentage >= 25:
        return "FX"
    else:
        return "F"


def calculate_gpa(results: List[Dict]) -> float:
    if not results:
        return 0.0

    total_points = 0
    total_credits = 0

    for r in results:
        test_type = r.get('test_type', 'test')
        credits = 3 if test_type == 'exam' else 2 if test_type in ['rk1', 'rk2'] else 1
        gpa = percentage_to_gpa(r.get('percentage', 0))
        total_points += gpa * credits
        total_credits += credits

    return round(total_points / total_credits, 2) if total_credits > 0 else 0.0


def calculate_test_score(test, answers: dict) -> Dict[str, float]:
    if not test or not answers:
        return {"score": 0, "max_score": test.max_score if test else 100, "percentage": 0}

    questions = test.questions
    if not questions:
        return {"score": 0, "max_score": test.max_score, "percentage": 0}

    total_score = 0
    max_score = test.max_score
    per_question_max = max_score / len(questions)

    for i, question in enumerate(questions):
        user_answer = answers.get(str(i), [])
        if not isinstance(user_answer, list):
            user_answer = [user_answer]

        variants = question.get("variants", [])
        correct_answers = question.get("correct_answers", [])
        difficulty = question.get("difficulty", "simple")

        weight = 1 if difficulty == "simple" else 2 if difficulty == "medium" else 3
        question_max = per_question_max * weight

        if not correct_answers:
            continue

        if question.get("type") == "single":
            if len(user_answer) > 0 and user_answer[0] in correct_answers:
                total_score += question_max
        else:
            n1 = len(correct_answers)
            n2 = len(variants) - n1

            if n2 == 0:
                if len(user_answer) == n1:
                    total_score += question_max
                continue

            k1 = sum(1 for idx in user_answer if idx in correct_answers)
            k2 = sum(1 for idx in user_answer if idx not in correct_answers)

            if k1 > 0:
                question_score = (question_max / 2) * (k1 / n1 + (n2 - k2) / n2)
                total_score += question_score

    percentage = (total_score / max_score) * 100 if max_score > 0 else 0
    return {
        "score": round(total_score, 2),
        "max_score": max_score,
        "percentage": round(percentage, 2)
    }


def parse_user_agent(user_agent: str) -> Dict[str, str]:
    result = {"browser": "Unknown", "os": "Unknown", "device": "Desktop"}

    if not user_agent:
        return result

    browser_patterns = [
        (r'Chrome/(\d+\.\d+)', 'Chrome'),
        (r'Firefox/(\d+\.\d+)', 'Firefox'),
        (r'Safari/(\d+\.\d+)', 'Safari'),
        (r'Edg/(\d+\.\d+)', 'Edge'),
        (r'MSIE (\d+\.\d+)', 'Internet Explorer'),
        (r'Trident/.*rv:(\d+\.\d+)', 'Internet Explorer')
    ]

    for pattern, browser_name in browser_patterns:
        if re.search(pattern, user_agent):
            result["browser"] = browser_name
            break

    os_patterns = [
        (r'Windows NT (\d+\.\d+)', 'Windows'),
        (r'Mac OS X (\d+[._]\d+)', 'macOS'),
        (r'Android (\d+\.\d+)', 'Android'),
        (r'iOS (\d+\.\d+)', 'iOS'),
        (r'iPhone', 'iOS'),
        (r'iPad', 'iOS'),
        (r'Linux', 'Linux')
    ]

    for pattern, os_name in os_patterns:
        if re.search(pattern, user_agent):
            result["os"] = os_name
            break

    if 'Mobile' in user_agent:
        result["device"] = 'Mobile'
    elif 'Tablet' in user_agent or 'iPad' in user_agent:
        result["device"] = 'Tablet'

    return result


async def save_upload_file(file, prefix: str = "") -> str:
    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = sanitize_filename(file.filename)
        filename = f"{prefix}_{timestamp}_{original_name}" if prefix else f"{timestamp}_{original_name}"
        file_path = upload_dir / filename

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"File saved: {file_path}")
        return str(file_path)
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        return ""


def sanitize_filename(filename: str) -> str:
    filename = filename.replace('/', '_').replace('\\', '_')
    filename = re.sub(r'[^\w\-_\. ]', '', filename)
    if len(filename) > 100:
        name, ext = os.path.splitext(filename)
        filename = name[:90] + ext
    return filename


def get_file_extension(filename: str) -> str:
    if '.' in filename:
        return filename.split('.')[-1].lower()
    return ''


def truncate_text(text: str, max_length: int = 100) -> str:
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def generate_random_password(length: int = 8) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(random.choice(chars) for _ in range(length))


def generate_token() -> str:
    return str(uuid.uuid4())


def hash_string(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def format_student_list(students: list, sort_by: str = 'name') -> list:
    if not students:
        return []

    sort_key = {
        'name': lambda x: x.get('full_name', ''),
        'iin': lambda x: x.get('iin', ''),
        'group': lambda x: x.get('group_name', ''),
        'score': lambda x: x.get('average_score', 0),
        'movements': lambda x: x.get('total_movements', 0)
    }.get(sort_by, lambda x: x.get('full_name', ''))

    reverse = sort_by in ['score', 'movements']
    return sorted(students, key=sort_key, reverse=reverse)