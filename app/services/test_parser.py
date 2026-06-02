"""
EduProctorAI - Test Parser
Parses test questions with format:
<question> - simple, <question2> - medium, <question3> - hard
<variant> - option, <variantright> - correct option
"""
import re
import random
import PyPDF2
import docx
import io
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TestParser:
    def parse_test(self, content: bytes, filename: str) -> List[Dict[str, Any]]:
        try:
            if filename.lower().endswith('.pdf'):
                text = self._extract_from_pdf(content)
            elif filename.lower().endswith('.docx'):
                text = self._extract_from_docx(content)
            else:
                for encoding in ['utf-8', 'cp1251', 'latin-1', 'utf-16']:
                    try:
                        text = content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    text = content.decode('utf-8', errors='ignore')
            return self._parse_text(text)
        except Exception as e:
            logger.error(f"Parse error for {filename}: {str(e)}")
            return []

    def extract_text(self, content: bytes, filename: str) -> str:
        try:
            if filename.lower().endswith('.pdf'):
                return self._extract_from_pdf(content)
            elif filename.lower().endswith('.docx'):
                return self._extract_from_docx(content)
            else:
                for encoding in ['utf-8', 'cp1251', 'latin-1']:
                    try:
                        return content.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return content.decode('utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Extract text error for {filename}: {str(e)}")
            return ""

    def _extract_from_pdf(self, content: bytes) -> str:
        text = ""
        try:
            pdf = PyPDF2.PdfReader(io.BytesIO(content))
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            logger.error(f"PDF extraction error: {str(e)}")
        return text

    def _extract_from_docx(self, content: bytes) -> str:
        text = ""
        try:
            doc = docx.Document(io.BytesIO(content))
            for para in doc.paragraphs:
                if para.text:
                    text += para.text + "\n"
        except Exception as e:
            logger.error(f"DOCX extraction error: {str(e)}")
        return text

    def _parse_text(self, text: str) -> List[Dict[str, Any]]:
        questions = []
        current_question = None
        current_variants = []
        current_difficulty = None
        current_correct = []

        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            if line.startswith('<question>'):
                if current_question and current_variants:
                    questions.append(self._create_question(
                        current_question, current_variants, 'simple', current_correct
                    ))
                current_question = line.replace('<question>', '').strip()
                current_difficulty = 'simple'
                current_variants = []
                current_correct = []
                i += 1
                continue

            elif line.startswith('<question2>'):
                if current_question and current_variants:
                    questions.append(self._create_question(
                        current_question, current_variants, 'medium', current_correct
                    ))
                current_question = line.replace('<question2>', '').strip()
                current_difficulty = 'medium'
                current_variants = []
                current_correct = []
                i += 1
                continue

            elif line.startswith('<question3>'):
                if current_question and current_variants:
                    questions.append(self._create_question(
                        current_question, current_variants, 'hard', current_correct
                    ))
                current_question = line.replace('<question3>', '').strip()
                current_difficulty = 'hard'
                current_variants = []
                current_correct = []
                i += 1
                continue

            elif line.startswith('<variantright>'):
                variant_text = line.replace('<variantright>', '').strip()
                idx = len(current_variants)
                current_variants.append({
                    'text': variant_text,
                    'correct': True,
                    'index': idx
                })
                current_correct.append(idx)
                i += 1
                continue

            elif line.startswith('<variant>'):
                variant_text = line.replace('<variant>', '').strip()
                idx = len(current_variants)
                is_correct = False
                if current_difficulty == 'simple' and not current_correct and len(current_variants) == 0:
                    is_correct = True
                    current_correct.append(idx)
                current_variants.append({
                    'text': variant_text,
                    'correct': is_correct,
                    'index': idx
                })
                i += 1
                continue

            elif current_question and not line.startswith('<'):
                current_question += " " + line
                i += 1
                continue

            i += 1

        if current_question and current_variants:
            questions.append(self._create_question(
                current_question, current_variants, current_difficulty or 'simple', current_correct
            ))

        return self._validate_questions(questions)

    def _create_question(self, text: str, variants: List[Dict], difficulty: str, correct: List[int]) -> Dict[str, Any]:
        import hashlib
        q_id = int(hashlib.md5(f"{text}{len(variants)}".encode()).hexdigest()[:8], 16) % 100000
        max_score = 1 if difficulty == 'simple' else 2 if difficulty == 'medium' else 3

        return {
            'id': q_id,
            'text': re.sub(r'\s+', ' ', text).strip(),
            'variants': variants,
            'difficulty': difficulty,
            'correct_answers': correct,
            'type': 'multiple' if len(correct) > 1 else 'single',
            'max_score': max_score,
            'variant_count': len(variants)
        }

    def _validate_questions(self, questions: List[Dict]) -> List[Dict]:
        valid = []
        for q in questions:
            if not q['variants']:
                continue
            if not q['correct_answers']:
                if q['difficulty'] == 'simple' and q['variants']:
                    q['variants'][0]['correct'] = True
                    q['correct_answers'] = [0]
                else:
                    continue
            q['variants'] = [v for v in q['variants'] if v['text'].strip()]
            if len(q['variants']) >= 2:
                valid.append(q)
        return valid

    def prepare_exam_questions(self, questions_rk1: List[Dict], questions_rk2: List[Dict]) -> List[Dict]:
        random.seed(42)
        simple1 = [q for q in questions_rk1 if q['difficulty'] == 'simple'][:15] if questions_rk1 else []
        medium1 = [q for q in questions_rk1 if q['difficulty'] == 'medium'][:5] if questions_rk1 else []
        hard1 = [q for q in questions_rk1 if q['difficulty'] == 'hard'][:5] if questions_rk1 else []
        simple2 = [q for q in questions_rk2 if q['difficulty'] == 'simple'][:15] if questions_rk2 else []
        medium2 = [q for q in questions_rk2 if q['difficulty'] == 'medium'][:5] if questions_rk2 else []
        hard2 = [q for q in questions_rk2 if q['difficulty'] == 'hard'][:5] if questions_rk2 else []

        result = simple1 + medium1 + hard1 + simple2 + medium2 + hard2
        random.shuffle(result)
        return result[:50]