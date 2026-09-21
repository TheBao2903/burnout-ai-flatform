"""
==============================================================
File: chat_response_generator.py

ChatResponseGenerator - Generate AI-powered responses for emotion chat.
==============================================================
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger("burnout.chat.response")

# System prompt for the psychologist persona
SYSTEM_PROMPT = """Ban la mot nha tam ly hoc chuyen nghiep, dang tu van cho nguoi dang trai qua burnout.

Nguyen tac:
1. The hien su dong cam va lang nghe chu dong
2. Hoi cau hoi mo de dao sau (probing questions)
3. Dua ra loi khuyen nhe nhang neu phu hop
4. KHONG phan xet, KHONG chan doan benh ly
5. Su dung ngon ngu Viet Nam, than thien, gan gui
6. Khuyen khich user chia se them

Cau truc phan hoi:
- Mo dau: The hien dong cam (1-2 cau)
- Than: Hoi cau hoi dao sau HOAC chia se insight ngan (2-3 cau)
- Ket thuc: Moi user chia se them (1 cau)
"""


@dataclass
class ChatAnalysisContext:
    """Context tu AI analysis cua message."""
    stress_score: float
    burnout_score: float
    fatigue_score: float
    detected_signals: List[str]
    keywords: List[str]
    sentiment: str


@dataclass
class ChatResponse:
    """Response tu AI chat generator."""
    content: str
    analysis_context: Optional[ChatAnalysisContext]
    follow_up_topic: Optional[str]


class ChatResponseGenerator:
    """Generate AI-powered responses for emotion chat."""

    def __init__(self, gemini_service=None):
        self._gemini = gemini_service

    def _get_gemini(self):
        """Lazy load Gemini service."""
        if self._gemini is None:
            from app.modules.assessment.services.gemini_service import get_gemini_service
            self._gemini = get_gemini_service()
        return self._gemini

    def generate_response(
        self,
        user_message: str,
        analysis_context: ChatAnalysisContext,
        conversation_history: List[dict] = None,
        message_count: int = 0,
    ) -> ChatResponse:
        """Generate a natural, empathetic response."""
        history_text = self._build_history_text(conversation_history or [])
        stage = self._determine_stage(message_count)
        analysis_summary = self._build_analysis_summary(analysis_context)
        prompt = self._build_prompt(
            user_message=user_message,
            history_text=history_text,
            analysis_summary=analysis_summary,
            stage=stage,
        )

        try:
            response_text = self._generate_with_gemini(prompt)
            return ChatResponse(
                content=response_text,
                analysis_context=analysis_context,
                follow_up_topic=self._extract_follow_up_topic(response_text),
            )
        except Exception as exc:
            logger.error("Failed to generate chat response: %s", exc)
            return self._generate_fallback_response(analysis_context)

    def _build_history_text(self, history: List[dict]) -> str:
        """Build readable history text for prompt."""
        if not history:
            return "Chua co lich su tro chuyen."

        lines = []
        for msg in history[-6:]:
            role = "Nguoi dung" if msg.get("role") == "user" else "Tu van vien"
            content = msg.get("content", "")[:200]
            lines.append(role + ": " + content)

        return "\n".join(lines)

    def _determine_stage(self, message_count: int) -> str:
        """Determine conversation stage based on message count."""
        if message_count <= 1:
            return "greeting"
        elif message_count <= 3:
            return "exploring"
        elif message_count <= 6:
            return "deepening"
        else:
            return "supporting"

    def _build_analysis_summary(self, ctx: ChatAnalysisContext) -> str:
        """Build analysis summary for prompt."""
        parts = [
            "- Muc stress: " + str(int(ctx.stress_score)) + "/100",
            "- Tín hieu burnout: " + str(int(ctx.burnout_score)) + "/100",
            "- Met moi: " + str(int(ctx.fatigue_score)) + "/100",
        ]

        if ctx.detected_signals:
            signals_str = ", ".join(ctx.detected_signals[:5])
            parts.append("- Tín hieu phat hien: " + signals_str)

        if ctx.keywords:
            keywords_str = ", ".join(ctx.keywords[:10])
            parts.append("- Tu khoa: " + keywords_str)

        parts.append("- Cam xuc: " + ctx.sentiment)

        return "\n".join(parts)

    def _build_prompt(
        self,
        user_message: str,
        history_text: str,
        analysis_summary: str,
        stage: str,
    ) -> str:
        """Build full prompt for Gemini."""
        stage_instruction = {
            "greeting": "Day la tin nhan dau tien. Hay chao hoi am ap va moi user chia se.",
            "exploring": "Dang kham pha van de. Hay hoi cau hoi mo ve cuoc song/cong viec cua user.",
            "deepening": "Dang dao sau. Hay hoi cau hoi cu the hon ve van de da ne.",
            "supporting": "Da hieu van de. Hay chia se chien luoc doi pho va hoi them neu can.",
        }

        prompt = """Ban la mot nha tam ly hoc chuyen nghiep. Dang tu van cho nguoi dang trai qua burnout.

{}

GIAI DOAN: {}

LICH SU TRO CHUYEN:
{}

PHAN TICH TIN NHAN MOI:
{}

TIN NHAN MOI CUA USER: "{}"

Hay tao phan hoi phu hop voi giai doan tro chuyen hien tai.
Phan hoi phai:
- Tu nhien, khong robotic
- Ngan gon (duoi 200 tu)
- Co hoi cau hoi mo de user chia se them
"""
        return prompt.format(
            SYSTEM_PROMPT,
            stage_instruction.get(stage, stage),
            history_text,
            analysis_summary,
            user_message,
        )

    def _generate_with_gemini(self, prompt: str) -> str:
        """Generate response using Gemini."""
        gemini = self._get_gemini()
        response = gemini.generate(
            prompt=prompt,
            temperature=0.7,
            max_output_tokens=300,
        )
        return response.text.strip()

    def _extract_follow_up_topic(self, response: str) -> Optional[str]:
        """Extract topic for follow-up from response."""
        if "?" in response:
            for sentence in response.split("."):
                if "?" in sentence:
                    return sentence.strip()[:100]
        return None

    def _generate_fallback_response(self, ctx: ChatAnalysisContext) -> ChatResponse:
        """Generate fallback template response if AI fails."""
        if ctx.sentiment == "negative" and ctx.stress_score > 60:
            content = (
                "Cam on ban da chia se. Toi hieu ban dang trai qua giai doan kho khan. "
                "Dieu do hoan toan binh thuong khi cuoc song co nhung luc ap luc nhu vay. "
                "Ban co the chia se them ve dieu gi dang khiến ban cam thay nhu vay khong?"
            )
        elif ctx.burnout_score > 60:
            content = (
                "Toi nhan thay ban dang co nhung dau hieu cua burnout. "
                "Dieu quan trong la ban da nhan ra dieu nay va tim kiem su ho tro. "
                "Ban co muon chia se them ve nhung gi dang xay ra trong cuoc song khong?"
            )
        else:
            content = (
                "Cam on ban da chia se! Toi dang lang nghe. "
                "Ban co muon ke them ve nhung dieu dang xay ra trong cuoc song khong?"
            )

        return ChatResponse(
            content=content,
            analysis_context=ctx,
            follow_up_topic=None,
        )


# Singleton
_generator: Optional[ChatResponseGenerator] = None


def get_chat_response_generator() -> ChatResponseGenerator:
    """Get singleton instance."""
    global _generator
    if _generator is None:
        _generator = ChatResponseGenerator()
    return _generator
