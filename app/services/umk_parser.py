"""
EduProctorAI - UMK (Educational Material) Parser
Extracts questions from control sections and lectures
Based on Korkyt Ata University UMK format
"""
import re
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class UMKParser:
    """
    Parses UMK documents to extract:
    - RK1 questions (Аралық бақылау №1)
    - RK2 questions (Аралық бақылау №2)
    - Final exam questions (IV. Қорытынды бағалаудың сұрақтары)
    - Lecture texts (Дәріс 1, Дәріс 2, etc.)
    """
    
    def __init__(self):
        self.rk1_patterns = [
            r'(?:№\s*1\s+Аралық\s+бақылау\s+сұрақтары|Аралық\s+бақылау\s+№\s*1)(.*?)(?=№\s*2\s+Аралық|Аралық\s+бақылау\s+№\s*2|IV\.|\Z)',
            r'(?:Аралық\s+бақылау\s+№\s*1)(.*?)(?=Аралық\s+бақылау\s+№\s*2|\Z)',
        ]
        
        self.rk2_patterns = [
            r'(?:№\s*2\s+Аралық\s+бақылау\s+сұрақтары|Аралық\s+бақылау\s+№\s*2)(.*?)(?=IV\.\s*Қорытынды|Қорытынды\s+бағалау|\Z)',
            r'(?:Аралық\s+бақылау\s+№\s*2)(.*?)(?=IV\.\s*Қорытынды|Қорытынды\s+бағалау|\Z)',
        ]
        
        self.final_patterns = [
            r'(?:IV\.\s*Қорытынды\s+бағалаудың\s+сұрақтары|Қорытынды\s+бағалау\s+сұрақтары|IV\.\s*Қорытынды\s+бағалау)(.*?)(?=V\.|\Z)',
            r'(?:Қорытынды\s+бағалау)(.*?)(?=V\.|\Z)',
        ]
        
        self.lecture_patterns = [
            r'(?:Дәріс\s+(\d+)|#\s*(\d+)\s+[Лл]екция)(.*?)(?=\n\s*(?:Дәріс|#\s*\d+\s+[Лл]екция|\n\d+\s+[Лл]екция|\Z))',
            r'(?:Лекция\s+(\d+))(.*?)(?=Лекция\s+\d+|\Z)',
        ]

    def parse_umk(self, text: str) -> Dict[str, Any]:
        result = {
            'rk1_questions': [],
            'rk2_questions': [],
            'final_questions': [],
            'all_questions': [],
            'lecture_texts': [],
            'lectures_by_number': {}
        }

        # Extract lectures
        lectures = self._extract_lectures(text)
        result['lecture_texts'] = lectures
        result['lectures_by_number'] = {str(lec['number']): lec['text'] for lec in lectures if 'number' in lec}
        
        # Extract RK1 questions
        for pattern in self.rk1_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                section_text = match.group(1)
                questions = self._extract_numbered_questions(section_text)
                if questions:
                    result['rk1_questions'] = questions
                    result['all_questions'].extend(questions)
                    logger.info(f"Extracted {len(questions)} RK1 questions")
                    break
        
        # Extract RK2 questions
        for pattern in self.rk2_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                section_text = match.group(1)
                questions = self._extract_numbered_questions(section_text)
                if questions:
                    result['rk2_questions'] = questions
                    result['all_questions'].extend(questions)
                    logger.info(f"Extracted {len(questions)} RK2 questions")
                    break
        
        # Extract Final questions
        for pattern in self.final_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                section_text = match.group(1)
                questions = self._extract_numbered_questions(section_text)
                if questions:
                    result['final_questions'] = questions
                    result['all_questions'].extend(questions)
                    logger.info(f"Extracted {len(questions)} Final questions")
                    break
        
        # Fallback: extract any numbered questions
        if not result['all_questions']:
            all_questions = self._extract_numbered_questions(text)
            result['all_questions'] = all_questions
            logger.info(f"Extracted {len(all_questions)} general questions")
        
        return result

    def _extract_lectures(self, text: str) -> List[Dict[str, Any]]:
        lectures = []
        
        for pattern in self.lecture_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                lec_num = None
                lec_text = None
                
                if len(match) == 2:
                    lec_num, lec_text = match
                elif len(match) == 3:
                    lec_num = match[0] or match[1]
                    lec_text = match[2]
                elif len(match) == 4:
                    lec_num = match[0] or match[1]
                    lec_text = match[3]
                
                if lec_num and lec_text and lec_text.strip():
                    lectures.append({
                        'number': int(lec_num),
                        'text': lec_text.strip()
                    })
        
        # Sort by number
        lectures.sort(key=lambda x: x['number'])
        
        # Fallback: split by "Дәріс" pattern
        if not lectures:
            lecture_sections = re.split(r'\n\s*(Дәріс\s+\d+[:\s]*|[Лл]екция\s+\d+[:\s]*)', text)
            for i in range(1, len(lecture_sections), 2):
                if i+1 < len(lecture_sections):
                    lec_num_match = re.search(r'(\d+)', lecture_sections[i])
                    if lec_num_match:
                        lectures.append({
                            'number': int(lec_num_match.group(1)),
                            'text': lecture_sections[i+1].strip()
                        })
        
        logger.info(f"Extracted {len(lectures)} lectures")
        return lectures

    def _extract_numbered_questions(self, text: str) -> List[Dict[str, Any]]:
        questions = []
        pattern = r'(?:^|\n)(\d+)[\.\)]+[:\s]*([^\n]+)'
        matches = re.findall(pattern, text)
        
        for num, q_text in matches:
            questions.append({
                'id': int(num),
                'text': q_text.strip(),
                'section': 'general'
            })
        
        return questions

    def _extract_keywords(self, text: str) -> List[str]:
        stop_words = {'the', 'and', 'or', 'of', 'to', 'in', 'for', 'with', 'by', 'is', 'are', 'was', 'what', 'how', 'why', 'when', 'where', 'which', 'who', 'whom', 'whose', 'this', 'that', 'these', 'those', 'a', 'an'}
        words = re.findall(r'\b[A-Za-z]{4,}\b', text)
        keywords = [w.lower() for w in words if w.lower() not in stop_words]
        return keywords[:10]

    def find_answer_in_lectures(self, question: str, lectures: List[Dict]) -> str:
        if not lectures:
            return ""
        
        keywords = self._extract_keywords(question)
        best_match = ""
        best_score = 0
        
        for lecture in lectures:
            lec_text = lecture.get('text', '')
            score = sum(1 for kw in keywords if kw.lower() in lec_text.lower())
            
            if score > best_score:
                best_score = score
                sentences = re.split(r'[.!?]+', lec_text)
                for sentence in sentences:
                    sent_score = sum(1 for kw in keywords if kw.lower() in sentence.lower())
                    if sent_score > 0 and len(sentence) < 500:
                        best_match = sentence.strip()
                        break
        
        if best_match and len(best_match) > 500:
            return best_match[:500] + "..."
        
        return best_match