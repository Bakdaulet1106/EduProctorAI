"""
EduProctorAI - AI Service for Question Generation
"""
import openai
import logging
import re
from typing import List, Dict, Any
from ..config import settings

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        if self.api_key:
            openai.api_key = self.api_key
        self.model = "gpt-3.5-turbo"

    async def generate_written_questions(self, text: str, test_type: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("OpenAI API key not configured, using fallback")
            return self._get_fallback_questions(test_type)

        if len(text) > 3000:
            text = text[:3000] + "..."

        num_questions = 3 if test_type in ["rk1", "rk2"] else 5

        lecture_range = "лекций 1-7" if test_type == "rk1" else "лекций 8-15" if test_type == "rk2" else "всех лекций"

        prompt = f"""
        На основе материала из {lecture_range} создайте {num_questions} письменных вопросов.
        Требования: вопросы должны быть четкими, проверять понимание ключевых концепций.
        Материал: {text}
        Верните только вопросы, каждый с новой строки, без нумерации.
        """

        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            content = response.choices[0].message.content
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            return [{"id": i+1, "text": line, "max_score": 10, "type": "written", "ai_generated": True} for i, line in enumerate(lines[:num_questions])]
        except Exception as e:
            logger.error(f"AI error: {e}")
            return self._get_fallback_questions(test_type)

    def _get_fallback_questions(self, test_type: str) -> List[Dict[str, Any]]:
        if test_type == "rk1":
            return [
                {"id": 1, "text": "Робототехника дегеніміз не және оның негізгі компоненттері қандай?", "max_score": 10, "type": "written"},
                {"id": 2, "text": "Arduino микроконтроллері қандай мақсатта қолданылады?", "max_score": 10, "type": "written"},
                {"id": 3, "text": "Қозғалтқыштарды басқарудың негізгі әдістері қандай?", "max_score": 10, "type": "written"}
            ]
        elif test_type == "rk2":
            return [
                {"id": 1, "text": "Табиғи сұрыптау принциптерінің негізгі идеясы қандай?", "max_score": 10, "type": "written"},
                {"id": 2, "text": "Эволюциялық алгоритмдердің робототехникадағы рөлі қандай?", "max_score": 10, "type": "written"},
                {"id": 3, "text": "Машиналық оқытуды автоматты басқаруда қалай қолдануға болады?", "max_score": 10, "type": "written"}
            ]
        else:
            return [
                {"id": 1, "text": "Робототехника дегеніміз не және оның негізгі компоненттері қандай?", "max_score": 10, "type": "written"},
                {"id": 2, "text": "Arduino микроконтроллері қандай мақсатта қолданылады?", "max_score": 10, "type": "written"},
                {"id": 3, "text": "Мобильді роботтардың түрлері мен қолдану салалары қандай?", "max_score": 10, "type": "written"},
                {"id": 4, "text": "3D модельдеу және басып шығару робототехникада қалай қолданылады?", "max_score": 10, "type": "written"},
                {"id": 5, "text": "Автономды роботтарды басқарудың негізгі принциптері қандай?", "max_score": 10, "type": "written"}
            ]