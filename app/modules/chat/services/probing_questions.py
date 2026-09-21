"""
==============================================================
File: probing_questions.py

ProbingQuestionsService - Generate follow-up questions based on user input.
==============================================================
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProbingQuestion:
    """Cau hoi dao sau."""
    topic: str
    question: str
    keywords: list


class ProbingQuestionsService:
    """Generate probing questions based on user input."""

    # Question templates by topic
    QUESTION_TEMPLATES = {
        "workload": [
            "Ban co the chia se them ve khoi luong cong viec hien tai khong?",
            "Nhung cong viec nao chiem nhieu thoi gian cua ban nhat?",
            "Ban co cam thay deadline dang bi qua tai khong?",
        ],
        "sleep": [
            "Ban ngu bao nhieu tieng moi dem?",
            "Chat luong giac ngu cua ban nhu the nao?",
            "Ban co gap kho khan gi khi ngu khong?",
        ],
        "stress": [
            "Dieu gi tao ra ap luc lon nhat cho ban luc nay?",
            "Ban cam thay stress nhat khi nao trong ngay?",
            "Co su kien cu the nao dang gay ra canh thang cho ban khong?",
        ],
        "fatigue": [
            "Ban co the mo ta muc do met moi cua minh khong?",
            "Khi nao ban cam thay met moi nhat trong ngay?",
            "Ban co dang thieu nang luong cho nhung hoat dong thuong ngay khong?",
        ],
        "emotion": [
            "Ban co the noi them ve cam xuc ma ban dang trai qua khong?",
            "Cam xuc nay xuat hien tu khi nao?",
            "Dieu gi lam cho cam xuc nay tot hon hoac tet hon?",
        ],
        "work_life": [
            "Ban co thoi gian cho ban than va gia dinh khong?",
            "Su can bang giua cong viec va cuoc song cua ban nhu the nao?",
            "Ban co lam viec ngoai gio thuong xuyen khong?",
        ],
        "support": [
            "Ban co nguoi than hoac ban be de chia se khong?",
            "Ban da tung tim kiem su ho tro tu chuyen gia chua?",
            "Ai hoac dieu gi giup ban cam thay tot hon?",
        ],
        "burnout_signs": [
            "Ban co cam thay minh dang kiet suc ca ve the chat lan tinh than khong?",
            "Ban con dam me voi cong viec nhu truoc khong?",
            "Ban co cam giac minh khong con hieu qua nhu truoc khong?",
        ],
    }

    # Keyword patterns to detect topics
    KEYWORD_PATTERNS = {
        "workload": [
            r"deadline",
            r"qua tai",
            r"nhieu viec",
            r"cong viec",
            r"lam them",
            r"tang ca",
        ],
        "sleep": [
            r"ngu",
            r"giac ngu",
            r"nghi ngoi",
            r"mat ngu",
            r"kho ngu",
            r"nang luong",
        ],
        "stress": [
            r"stress",
            r"can thang",
            r"lo lang",
            r"lo au",
            r"ap luc",
        ],
        "fatigue": [
            r"met",
            r"met moi",
            r"kiet suc",
            r"burnout",
            r"uets oai",
        ],
        "emotion": [
            r"cam xuc",
            r"buon",
            r"vui",
            r"gian",
            r"tuc",
        ],
        "work_life": [
            r"can bang",
            r"gia dinh",
            r"ban be",
            r"thoi gian",
        ],
        "support": [
            r"ho tro",
            r"giup do",
            r"tam su",
            r"chia se",
        ],
        "burnout_signs": [
            r"burnout",
            r"kiet suc",
            r"chan",
            r"ng an",
            r"dam me",
        ],
    }

    def __init__(self):
        self._used_questions = {}

    def get_probing_question(
        self,
        user_message: str,
        analysis_context: dict,
        assessment_id: str,
    ) -> Optional[ProbingQuestion]:
        """Get a probing question based on user message."""
        topics = self._detect_topics(user_message)

        if not topics:
            return self._get_general_followup()

        primary_topic = topics[0]
        question = self._get_question_for_topic(primary_topic, assessment_id)

        if question:
            return ProbingQuestion(
                topic=primary_topic,
                question=question,
                keywords=self.KEYWORD_PATTERNS.get(primary_topic, []),
            )

        return None

    def _detect_topics(self, message: str) -> list:
        """Detect topics in user message based on keywords."""
        message_lower = message.lower()
        topic_scores = {}

        for topic, keywords in self.KEYWORD_PATTERNS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                topic_scores[topic] = score

        sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, score in sorted_topics]

    def _get_question_for_topic(self, topic: str, assessment_id: str) -> Optional[str]:
        """Get a non-repeated question for the topic."""
        questions = self.QUESTION_TEMPLATES.get(topic, [])
        if not questions:
            return None

        if assessment_id not in self._used_questions:
            self._used_questions[assessment_id] = set()

        used = self._used_questions[assessment_id]

        for i, question in enumerate(questions):
            if i not in used:
                used.add(i)
                return question

        used.clear()
        used.add(0)
        return questions[0]

    def _get_general_followup(self) -> ProbingQuestion:
        """Get a general follow-up question."""
        return ProbingQuestion(
            topic="general",
            question="Ban co muon chia se them ve dieu gi khong? Toi dang lang nghe.",
            keywords=[],
        )

    def clear_assessment_questions(self, assessment_id: str):
        """Clear used questions for an assessment."""
        if assessment_id in self._used_questions:
            del self._used_questions[assessment_id]


# Singleton
_probing_service: Optional[ProbingQuestionsService] = None


def get_probing_questions_service() -> ProbingQuestionsService:
    """Get singleton instance."""
    global _probing_service
    if _probing_service is None:
        _probing_service = ProbingQuestionsService()
    return _probing_service
