"""
EduProctorAI - Anti-Plagiarism Module
"""
import re
import hashlib
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AntiPlagiarism:
    ZWSP = '\u200B'
    ZWNJ = '\u200C'
    ZWJ = '\u200D'
    INVISIBLE_CHARS = [ZWSP, ZWNJ, ZWJ]

    @classmethod
    def similarity(cls, text1: str, text2: str, k: int = 5) -> float:
        if not text1 or not text2:
            return 0.0

        def get_shingles(txt: str, shingle_len: int = k) -> set:
            txt = re.sub(r'\s+', ' ', txt.lower())
            txt = re.sub(r'[^\w\s]', '', txt)
            if len(txt) < shingle_len:
                return {txt}
            return {txt[i:i+shingle_len] for i in range(len(txt) - shingle_len + 1)}

        sh1 = get_shingles(text1)
        sh2 = get_shingles(text2)

        if not sh1 or not sh2:
            return 0.0

        intersection = len(sh1 & sh2)
        union = len(sh1 | sh2)
        return intersection / union if union > 0 else 0.0

    @classmethod
    def check_against_reference(cls, student_answer: str, reference_answer: str) -> Dict[str, Any]:
        if not reference_answer:
            return {'similarity': 0.0, 'is_suspicious': False, 'message': 'No reference answer'}

        sim = cls.similarity(student_answer, reference_answer)
        is_suspicious = sim > 0.7
        
        return {
            'similarity': round(sim, 3),
            'is_suspicious': is_suspicious,
            'message': 'Strong similarity to reference answer detected' if is_suspicious else 'Original answer'
        }

    @classmethod
    def add_watermark(cls, text: str, user_id: int, test_id: int) -> str:
        watermark = f"UID{user_id}TID{test_id}"
        hash_part = hashlib.md5(watermark.encode()).hexdigest()[:16]
        binary = ''.join(format(ord(c), '08b') for c in hash_part)
        invisible = ''.join(cls.ZWSP if b == '0' else cls.ZWNJ for b in binary)
        return invisible + text

    @classmethod
    def extract_watermark(cls, text: str) -> str:
        invisible = ''.join(c for c in text if c in cls.INVISIBLE_CHARS)
        if not invisible:
            return ''
        binary = ''.join('0' if c == cls.ZWSP else '1' for c in invisible)
        chars = []
        for i in range(0, len(binary), 8):
            byte = binary[i:i+8]
            if len(byte) == 8:
                try:
                    chars.append(chr(int(byte, 2)))
                except ValueError:
                    pass
        return ''.join(chars)

    @classmethod
    def full_report(cls, answers: Dict[int, str], reference_answers: Dict[int, str], all_answers: List[Dict]) -> Dict[str, Any]:
        report = {
            'total_questions': len(answers),
            'suspicious_count': 0,
            'average_similarity': 0.0,
            'details': [],
            'summary': 'No plagiarism detected'
        }

        total_sim = 0.0

        for q_id, ans in answers.items():
            ref_ans = reference_answers.get(q_id, '')
            check = cls.check_against_reference(ans, ref_ans)
            
            total_sim += check['similarity']
            
            if check['is_suspicious']:
                report['suspicious_count'] += 1
                report['details'].append({
                    'question_id': q_id,
                    'similarity_to_reference': check['similarity'],
                    'warning': check['message']
                })

        if report['total_questions'] > 0:
            report['average_similarity'] = round(total_sim / report['total_questions'], 3)

        if report['suspicious_count'] > 0:
            report['summary'] = f"Detected {report['suspicious_count']} suspicious answers. Average similarity to reference: {report['average_similarity'] * 100:.1f}%"

        return report