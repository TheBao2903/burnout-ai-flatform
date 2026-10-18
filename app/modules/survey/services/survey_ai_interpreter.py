"""
==============================================================
File: survey_ai_interpreter.py

SurveyAIInterpreter - Tầng 3 (AI Interpretation) sử dụng Gemini API.

Nhiệm vụ:
- Tiếp nhận dữ liệu định lượng và bằng chứng bối cảnh từ Tầng 1 & Tầng 2:
  + Kết quả khảo sát (8 câu Daily Pulse hoặc 16 câu OLBI)
  + 12 Nhóm ngành nghề chuẩn hóa (Industry Archetypes)
  + 6 Hình mẫu tổ hợp năng lượng chéo (Cross-Metric Archetypes)
- Sử dụng Gemini LLM sinh nhận định cá nhân hóa tự nhiên, thấu cảm, giàu tính chuyên môn.
- ĐẢM BẢO: KHÔNG đọc lại con số khô khan (người dùng đã nhìn thấy ở UI).
- ĐẢM BẢO: KHÔNG dùng từ ngữ chẩn đoán y khoa hay khẳng định nguyên nhân nhân quả chắc chắn.
- Trả về JSON Schema chuẩn:
  {
    "current_state_text": "...",
    "change_text": "...",
    "contributing_factors_text": "...",
    "reflection_question": "...",
    "suggested_chat_prompt": "..."
  }
==============================================================
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("burnout.survey.interpreter")


@dataclass
class AIInsightResult:
    """Kết quả phân tích định tính từ Gemini AI (Tầng 3)."""

    current_state_text: str
    change_text: str
    contributing_factors_text: str
    reflection_question: str
    suggested_chat_prompt: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "current_state_text": self.current_state_text,
            "change_text": self.change_text,
            "contributing_factors_text": self.contributing_factors_text,
            "reflection_question": self.reflection_question,
            "suggested_chat_prompt": self.suggested_chat_prompt,
        }


SYSTEM_PROMPT = """Bạn là một Chuyên gia Đồng hành Sức khỏe Tinh thần Nơi Làm Việc (AI Workplace Wellbeing Companion) ấm áp, tinh tế và thấu cảm.
Nhiệm vụ của bạn là nhận dữ liệu bối cảnh khảo sát trạng thái (gồm cả khảo sát vi mô hàng ngày và khảo sát định kỳ) kết hợp với hồ sơ ngành nghề và hình mẫu năng lượng để viết nhận định cá nhân hóa theo ngôn ngữ nói tự nhiên, chân thành.

NGUYÊN TẮC QUAN TRỌNG:
1. KHÔNG ĐỌC LẠI CON SỐ/CHỈ SỐ KHÔ KHAN (Ví dụ KHÔNG nói "Điểm kiệt sức 3.4/5" hay "Bạn quá tải 2/4 lần" vì người dùng đã nhìn thấy con số ở UI rồi). Hãy dịch con số thành CẢM GIÁC THỰC TẾ và TRẠNG THÁI NĂNG LƯỢNG theo đúng đặc thù nghề nghiệp của họ.
2. KHÔNG CHẨN ĐOÁN Y KHOA (Không phán "Bạn bị burnout", "Bạn bị trầm cảm").
3. KHÔNG KHẲNG ĐỊNH NGUYÊN NHÂN NHÂN QUẢ CHẮC CHẮN (Dùng các từ "có thể liên quan đến", "dường như đang ảnh hưởng", "cho thấy nhu cầu nghỉ ngơi đang gia tăng").
4. BÁM SÁT NGỮ CẢNH NGÀNH NGHỀ & HÌNH MẪU TÂM LÝ: Vận dụng đúng thuật ngữ và nỗi niềm đặc trưng của ngành nghề được cung cấp, nói đúng giọng điệu thấu cảm của hình mẫu năng lượng.
5. VĂN PHONG TỰ NHIÊN, THẤU CẢM, DỄ TIẾP NHẬN: Giống như một người bạn tri kỷ hoặc cố vấn tâm lý tinh tế đang trò chuyện cùng người dùng.

YÊU CẦU ĐẦU RA JSON BẮT BUỘC (Trả về duy nhất 1 JSON object):
{
  "current_state_text": "2-3 câu diễn giải trạng thái hiện tại một cách tự nhiên, thấu cảm theo nhịp độ nghề nghiệp của người dùng.",
  "change_text": "1-2 câu quan sát sự thay đổi so với các lần đánh giá trước một cách đời thường.",
  "contributing_factors_text": "2-3 câu nêu các yếu tố có thể liên quan (deadline ngành, áp lực chỉ tiêu/sửa đổi/trực ca, giấc ngủ, phục hồi...).",
  "reflection_question": "1 câu hỏi gợi mở suy ngẫm sâu sắc đánh trúng trọng tâm công việc và cuộc sống của họ.",
  "suggested_chat_prompt": "1 câu prompt ngắn để nạp sang AI Chat khi người dùng bấm Khám phá cùng AI."
}
"""


class SurveyAIInterpreter:
    """Interpreter sử dụng Gemini API để sinh nhận định cá nhân hóa theo ngành nghề và hình mẫu."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None

    def _get_gemini(self) -> Optional[Any]:
        """Lazy load Gemini client."""
        if self._client is not None:
            return self._client

        from app.core.settings import get_settings
        settings = get_settings().google_ai
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or settings.api_key
        if not api_key:
            logger.warning("GEMINI_API_KEY / GOOGLE_API_KEY is not set. SurveyAIInterpreter will use fallback.")
            return None

        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
            return self._client
        except Exception as e:
            logger.error("Failed to initialize Google GenAI Client: %s", e)
            return None

    def generate_insight(self, evidence: Dict[str, Any]) -> AIInsightResult:
        """Sinh nhận định cá nhân hóa từ bằng chứng dữ liệu khảo sát."""
        client = self._get_gemini()
        if not client:
            return self._generate_fallback(evidence)

        try:
            prompt = self._build_prompt(evidence)
            from app.core.settings import get_settings
            settings = get_settings().google_ai

            response = client.models.generate_content(
                model=settings.model,
                contents=prompt,
                config={
                    "temperature": 0.75,
                    "response_mime_type": "application/json",
                },
            )

            if hasattr(response, "text") and response.text:
                data = json.loads(response.text.strip())
                return AIInsightResult(
                    current_state_text=data.get("current_state_text", "").strip(),
                    change_text=data.get("change_text", "").strip(),
                    contributing_factors_text=data.get("contributing_factors_text", "").strip(),
                    reflection_question=data.get("reflection_question", "").strip(),
                    suggested_chat_prompt=data.get("suggested_chat_prompt", "").strip(),
                )
        except Exception as e:
            logger.error("Gemini Survey AI Interpretation failed: %s", e)

        return self._generate_fallback(evidence)

    def _build_prompt(self, evidence: Dict[str, Any]) -> str:
        """Dựng prompt truyền bằng chứng đa chiều cho Gemini."""
        job_title = evidence.get("job_title", "Chuyên viên")
        industry_name = evidence.get("industry_name", "Văn phòng & Chuyên môn")
        vocab_hints = evidence.get("vocabulary_hints", [])
        stressors_ctx = evidence.get("stressors_context", "")
        archetype_name = evidence.get("archetype_name", "Cân bằng & Chủ động")
        empathy_dir = evidence.get("empathy_direction", "")
        ai_instruction = evidence.get("ai_prompt_instruction", "")

        prompt = f"""{SYSTEM_PROMPT}

HỒ SƠ NGHỀ NGHIỆP CỦA NGƯỜI DÙNG:
- Vị trí / Chức danh: {job_title}
- Nhóm ngành nghề: {industry_name}
- Áp lực ngành đặc thù: {stressors_ctx}
- Thuật ngữ ngữ cảnh gợi ý: {', '.join(vocab_hints) if vocab_hints else 'áp lực tiến độ, tái tạo năng lượng'}

CHẨN ĐOÁN HÌNH MẪU NĂNG LƯỢNG (CROSS-METRIC ARCHETYPE):
- Hình mẫu: {archetype_name}
- Định hướng thấu cảm: {empathy_dir}
- Chỉ dẫn riêng cho AI: {ai_instruction}

BẰNG CHỨNG KHẢO SÁT THỰC TẾ:
- Trạng thái kiệt sức: {evidence.get('exhaustion_level', 'trung bình')}
- Mức độ gắn kết: {evidence.get('disengagement_level', 'trung bình')}
- Giấc ngủ: {evidence.get('sleep_hours', 7)} giờ (Đánh giá hồi phục sáng: {evidence.get('recovery_score', 3)}/5)
- Mức quá tải gần đây: {evidence.get('quick_overload', 2)}/5
- Các lý do quá tải ghi nhận: {', '.join(evidence.get('overload_reasons', [])) or 'Không có'}
- Ghi chú riêng từ người dùng: {evidence.get('other_reason', 'Không có')}
- Dữ liệu so sánh với lần trước: {evidence.get('previous_comparison', 'Đây là lần khảo sát đầu tiên')}
- Xu hướng lịch sử: {evidence.get('trend_summary', 'Chưa có đủ lịch sử')}

Hãy phân tích và xuất ra duy nhất 1 đối tượng JSON theo cấu trúc yêu cầu trên.
"""
        return prompt

    def _generate_fallback(self, evidence: Dict[str, Any]) -> AIInsightResult:
        """Sinh nhận định tự nhiên mặc định theo ngành nghề và hình mẫu khi không gọi được Gemini."""
        ex_level = evidence.get("exhaustion_level", "medium")
        reasons = evidence.get("overload_reasons", [])
        sleep = evidence.get("sleep_hours", 7)
        rec = evidence.get("recovery_score", 3)
        job_title = evidence.get("job_title", "công việc")
        industry_name = evidence.get("industry_name", "")
        reflection_starter = evidence.get("reflection_theme")

        if ex_level in ("high", "critical"):
            current = (
                f"Áp lực từ vị trí {job_title} dạo gần đây dường như đang đòi hỏi nhiều sự tập trung và gắng sức, "
                f"khiến năng lượng của bạn bị sụt giảm nhanh hơn bình thường. Cơ thể bạn đang phát đi những tín hiệu cần nghỉ ngơi và nạp lại năng lượng chủ động."
            )
        else:
            current = (
                f"Trạng thái năng lượng của bạn trong vị trí {job_title} hiện tại tương đối cân bằng, "
                f"tuy nhiên vẫn có những thời điểm nhịp độ công việc khiến bạn cảm thấy hơi uể oải vào cuối ngày."
            )

        if "deadline" in str(reasons).lower() or "overtime" in str(reasons).lower():
            factors = (
                "Áp lực tiến độ dồn dập kết hợp với thời gian làm việc kéo dài dường như đang là yếu tố chính tác động trực tiếp đến khả năng phục hồi của bạn."
            )
        elif rec <= 2 or sleep < 6:
            factors = (
                "Chất lượng giấc ngủ và cảm giác nạp lại năng lượng chưa thật sự trọn vẹn vào đầu ngày có thể đang khiến bạn dễ bị mệt mỏi hơn bình thường."
            )
        else:
            factors = (
                f"Đặc thù khối lượng công việc trong mảng {industry_name or 'này'} cùng việc thiếu hụt các khoảng nghỉ ngắn dường như đang ảnh hưởng nhẹ đến sự tập trung của bạn."
            )

        change = (
            "So với các lần đánh giá trước, nhu cầu nghỉ ngơi và giải tỏa áp lực của bạn đang có xu hướng đáng chú ý hơn."
        )

        ref_q = reflection_starter or f"Bạn có nhận thấy dạo này mình cần nhiều thời gian hơn để phục hồi sau một ngày làm {job_title} không?"
        prompt_str = f"Tôi muốn tâm sự thêm về áp lực trong công việc {job_title} và cảm giác mệt mỏi dạo gần đây."

        return AIInsightResult(
            current_state_text=current,
            change_text=change,
            contributing_factors_text=factors,
            reflection_question=ref_q,
            suggested_chat_prompt=prompt_str,
        )


_interpreter_instance: Optional[SurveyAIInterpreter] = None


def get_survey_ai_interpreter() -> SurveyAIInterpreter:
    global _interpreter_instance
    if _interpreter_instance is None:
        _interpreter_instance = SurveyAIInterpreter()
    return _interpreter_instance
