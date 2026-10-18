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
        "Xin chào! Rất vui được trò chuyện cùng bạn. Hôm nay công việc và tâm trạng của bạn thế nào?",
        "Chào bạn! Tôi ở đây để lắng nghe và luôn đồng hành cùng bạn. Hãy thoải mái chia sẻ những điều bạn đang bận tâm hôm nay nhé.",
        "Chào bạn! Cảm ơn bạn đã tìm đến tôi. Hãy trải lòng về những áp lực hay cảm xúc bạn đang trải qua nhé.",
    ]

    # Closing templates
    CLOSING_MESSAGES = [
        "Cảm ơn bạn đã tin tưởng chia sẻ những điều rất riêng tư với tôi. Hãy nhớ rằng việc nhận biết và chăm sóc sức khỏe tinh thần của bản thân là cực kỳ quan trọng. Nếu bạn cần, tôi luôn ở đây để lắng nghe.",
        "Cảm ơn bạn đã chia sẻ cùng tôi. Hãy dành thời gian lắng nghe và nghỉ ngơi phục hồi cơ thể nhé. Chúc bạn một ngày nhẹ nhàng và bình an!",
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
                    message = message + "\n\n📋 Tóm tắt nội dung trao đổi: " + points[0] + "."

            if summary.get("recommendations"):
                recs = summary["recommendations"]
                if recs:
                    message = message + "\n\n💡 Gợi ý hành động cho bạn: " + recs[0] + "."

        return message

    def should_wrap_up(
        self,
        assessment_id: str,
        message_count: int,
        analysis_context: dict,
    ) -> tuple[bool, Optional[str]]:
        """Determine if conversation should wrap up based on STA session discipline."""
        stage = self.get_current_stage(assessment_id, message_count)

        if stage == ConversationStage.WRAPPING_UP:
            return True, "Đã đạt đến giai đoạn kết thúc tự nhiên của cuộc trò chuyện."

        burnout_score = analysis_context.get("burnout_score", 0)
        stress_score = analysis_context.get("stress_score", 0)

        # Ngăn đóng phiên đột ngột nếu người dùng đang có dấu hiệu căng thẳng cực đoan (cần an ủi thêm)
        if burnout_score > 85 or stress_score > 90:
            if message_count < 8:
                return False, None

        # STA Elastic 4+2 Discipline:
        # Lượt 4: Cổng đánh giá kết thúc sớm nếu đã đủ dữ liệu
        if message_count >= 4 and stage in [ConversationStage.COPING, ConversationStage.WRAPPING_UP]:
            return True, "Đã có đủ dữ liệu bối cảnh và đưa ra hành động hỗ trợ phù hợp."

        # Lượt 6: Trần cứng bắt buộc kết thúc phiên
        if message_count >= 6:
            return True, "Phiên trò chuyện đã đạt giới hạn tối ưu (Trần Lượt 6), tiến hành tổng hợp để người dùng nghỉ ngơi."

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
            key_points.append("Tín hiệu ghi nhận: " + ", ".join(signals))

        if analysis_context.get("stress_score", 0) > 60:
            key_points.append("Mức độ căng thẳng đáng chú ý cần được quan tâm điều hòa")
            recommendations.append("Thực hành bài tập thở sâu hoặc thư giãn cơ bắp ngắn hạn")

        if analysis_context.get("burnout_score", 0) > 50:
            key_points.append("Có tín hiệu kiệt sức công việc cần được theo dõi chủ động")
            recommendations.append("Ưu tiên nghỉ ngơi và ngắt kết nối khỏi các thiết bị công việc sau giờ làm")

        if analysis_context.get("fatigue_score", 0) > 60:
            recommendations.append("Đảm bảo giấc ngủ đủ và chất lượng để cơ thể hồi phục")

        user_messages = [m for m in conversation_history if m.get("role") == "user"]
        if len(user_messages) < 3:
            recommendations.append("Duy trì việc theo dõi năng lượng đều đặn mỗi ngày")

        if analysis_context.get("burnout_score", 0) > 70:
            overall = "Tín hiệu kiệt sức ở mức cao - Hãy ưu tiên giảm tải và trao đổi cùng người có chuyên môn"
        elif analysis_context.get("burnout_score", 0) > 50:
            overall = "Có tín hiệu kiệt sức cần lưu ý theo dõi và điều chỉnh nhịp làm việc"
        else:
            overall = "Trạng thái năng lượng hiện tại đang ở mức ổn định"

        return {
            "key_points": key_points if key_points else ["Chưa có đủ thông tin để tóm tắt chi tiết"],
            "recommendations": recommendations if recommendations else ["Tiếp tục duy trì chăm sóc sức khỏe tinh thần"],
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
