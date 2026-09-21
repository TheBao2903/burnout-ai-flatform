"""
==============================================================
File: conversation_stages.py

ConversationStages - Manage conversation flow through therapeutic stages.

Features:
- Track conversation stage progression
- Provide stage-appropriate greetings
- Generate closing summaries
- Determine when to wrap up conversation

Separated for clean architecture.
==============================================================
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ConversationStage(Enum):
    """Cac giai doan cua cuoc tro chuyen."""
    GREETING = "greeting"
    EXPLORING = "exploring"
    DEEPENING = "deepening"
    COPING = "coping"
    WRAPPING_UP = "wrapping_up"


@dataclass
class StageInfo:
    """Thong tin ve mot giai doan."""
    stage: ConversationStage
    name: str
    description: str
    expected_messages: int
    can_transition_to: list


class ConversationStagesService:
    """
    Manage conversation through therapeutic stages.

    The conversation typically flows:
    GREETING -> EXPLORING -> DEEPENING -> COPING -> WRAPPING_UP
    """

    # Stage definitions
    STAGES = {
        ConversationStage.GREETING: StageInfo(
            stage=ConversationStage.GREETING,
            name="Chao hoi",
            description="Xay dung rapport va tao khong khi an toan",
            expected_messages=1,
            can_transition_to=[ConversationStage.EXPLORING],
        ),
        ConversationStage.EXPLORING: StageInfo(
            stage=ConversationStage.EXPLORING,
            name="Kham pha",
            description="Tim hieu van de va hoan canh cua user",
            expected_messages=3,
            can_transition_to=[ConversationStage.DEEPENING, ConversationStage.GREETING],
        ),
        ConversationStage.DEEPENING: StageInfo(
            stage=ConversationStage.DEEPENING,
            name="Dao sau",
            description="Dao sau vao van de cu the",
            expected_messages=6,
            can_transition_to=[ConversationStage.COPING, ConversationStage.EXPLORING],
        ),
        ConversationStage.COPING: StageInfo(
            stage=ConversationStage.COPING,
            name="Doi pho",
            description="Chia se chien luoc va ky nang",
            expected_messages=10,
            can_transition_to=[ConversationStage.WRAPPING_UP, ConversationStage.DEEPENING],
        ),
        ConversationStage.WRAPPING_UP: StageInfo(
            stage=ConversationStage.WRAPPING_UP,
            name="Ket thuc",
            description="Tom tat va dua ra huong dan",
            expected_messages=15,
            can_transition_to=[],
        ),
    }

    # Greeting templates
    GREETING_MESSAGES = [
        "Xin chao! Rat vui duoc tro chuyen voi ban. Ban cam thay nhu the nao hom nay?",
        "Chao ban! Toi o day de lang nghe va ho tro ban. Ban muon chia se dieu gi hom nay?",
        "Chao ban! Cam on da den day. Hay thoai mai chia se nhung gi ban dang trai qua.",
    ]

    # Closing templates
    CLOSING_MESSAGES = [
        "Cam on ban da chia se nhung dieu rất rieng tu. Hay nho rang viec nhan biet va cham soc ban than la rất quan trong. Neu ban can, toi luon o day de lang nghe.",
        "Cam on ban da tin tuong chia se voi toi. Hay tiep tuc chu y den suc khoe tinh than cua minh nhe. Tam biet va chuc ban mot ngay tot lam!",
    ]

    def __init__(self):
        self._stage_history = {}

    def get_current_stage(self, assessment_id: str, message_count: int) -> ConversationStage:
        """Determine current stage based on message count."""
        if message_count <= 1:
            return ConversationStage.GREETING
        elif message_count <= 3:
            return ConversationStage.EXPLORING
        elif message_count <= 6:
            return ConversationStage.DEEPENING
        elif message_count <= 10:
            return ConversationStage.COPING
        else:
            return ConversationStage.WRAPPING_UP

    def get_stage_info(self, stage: ConversationStage) -> StageInfo:
        """Get information about a stage."""
        return self.STAGES.get(stage, self.STAGES[ConversationStage.GREETING])

    def get_greeting_message(self) -> str:
        """Get a greeting message."""
        return random.choice(self.GREETING_MESSAGES)

    def get_closing_message(self, summary: Optional[dict] = None) -> str:
        """Get a closing message, optionally including a summary."""
        message = random.choice(self.CLOSING_MESSAGES)

        if summary:
            if summary.get("key_points"):
                points = summary["key_points"]
                if points:
                    message = message + "\n\nTom tat nhung dieu chung ta da thao luan: " + points[0] + "."

            if summary.get("recommendations"):
                recs = summary["recommendations"]
                if recs:
                    message = message + "\n\nGoỵ y cho ban: " + recs[0] + "."

        return message

    def should_wrap_up(
        self,
        assessment_id: str,
        message_count: int,
        analysis_context: dict,
    ) -> tuple[bool, Optional[str]]:
        """Determine if conversation should wrap up."""
        stage = self.get_current_stage(assessment_id, message_count)

        if stage == ConversationStage.WRAPPING_UP:
            return True, "Da dat den giai doan ket thuc tu nhien cua cuoc tro chuyen."

        burnout_score = analysis_context.get("burnout_score", 0)
        stress_score = analysis_context.get("stress_score", 0)

        if burnout_score > 80 or stress_score > 85:
            return False, None

        if stage == ConversationStage.COPING and message_count >= 8:
            return True, "Da co du thong tin de tom tat va dua ra goỵ y."

        if message_count >= 12:
            return True, "Cuoc tro chuyen da keo dai, hay tom tat."

        return False, None

    def generate_summary(
        self,
        conversation_history: list,
        analysis_context: dict,
    ) -> dict:
        """Generate a summary of the conversation."""
        key_points = []
        recommendations = []

        if analysis_context.get("detected_signals"):
            signals = analysis_context["detected_signals"][:3]
            key_points.append("Ban dang trai qua: " + ", ".join(signals))

        if analysis_context.get("stress_score", 0) > 60:
            key_points.append("Muc do stress dang chu y can duoc quan ly")
            recommendations.append("Hay thuc hanh cac bai tap thở va thien de giam stress")

        if analysis_context.get("burnout_score", 0) > 50:
            key_points.append("Co dau hieu burnout can duoc chu y")
            recommendations.append("Uu tien nghi ngoi va can bang cuoc song")

        if analysis_context.get("fatigue_score", 0) > 60:
            recommendations.append("Dam bao ngu du 7-8 tieng moi dem")

        user_messages = [m for m in conversation_history if m.get("role") == "user"]
        if len(user_messages) < 3:
            recommendations.append("Hay tiep tuc chia se de chung ta hieu ro hon ve tinh trang cua ban")

        if analysis_context.get("burnout_score", 0) > 70:
            overall = "Muc do burnout nghiem trong - nen tim kiem ho tro chuyen nghiep"
        elif analysis_context.get("burnout_score", 0) > 50:
            overall = "Co dau hieu burnout can duoc theo doi va quan ly"
        else:
            overall = "Tinh trang o muc co the quan ly duoc"

        return {
            "key_points": key_points if key_points else ["Chua co thong tin du de tom tat"],
            "recommendations": recommendations if recommendations else ["Tiep tuc cham soc suc khoe tinh than"],
            "overall_assessment": overall,
        }

    def record_stage_transition(
        self,
        assessment_id: str,
        from_stage: ConversationStage,
        to_stage: ConversationStage
    ):
        """Record a stage transition for analytics."""
        if assessment_id not in self._stage_history:
            self._stage_history[assessment_id] = []

        self._stage_history[assessment_id].append({
            "from": from_stage.value,
            "to": to_stage.value,
        })

    def get_conversation_summary(self, assessment_id: str) -> Optional[dict]:
        """Get summary of conversation stages for an assessment."""
        if assessment_id not in self._stage_history:
            return None

        transitions = self._stage_history[assessment_id]
        if not transitions:
            return None

        return {
            "transitions": transitions,
            "stages_visited": list(set(t["to"] for t in transitions)),
        }


# Singleton
_stages_service: Optional[ConversationStagesService] = None


def get_conversation_stages_service() -> ConversationStagesService:
    """Get singleton instance."""
    global _stages_service
    if _stages_service is None:
        _stages_service = ConversationStagesService()
    return _stages_service
