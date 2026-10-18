"""
==============================================================
File: chat_response_generator.py

ChatResponseGenerator - Generate AI-powered responses for emotion chat.
==============================================================
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Any

logger = logging.getLogger("burnout.chat.response")

# System prompt for the psychologist persona according to STA standards
SYSTEM_PROMPT = """Bạn là một chuyên gia đồng hành sức khỏe tinh thần và tham vấn tâm lý công việc chuyên nghiệp (STA Psychological Advisor), ấm áp, tinh tế và tôn trọng tuyệt đối dữ liệu thực chứng.

NGUYÊN TẮC BẮT BUỘC:
1. LUÔN BẮT BUỘC TRẢ LỜI BẰNG TIẾNG VIỆT CÓ DẤU CHUẨN XÁC 100%, ĐÚNG CHÍNH TẢ, TỰ NHIÊN, KHÔNG BAO GIỜ DÙNG TIẾNG VIỆT KHÔNG DẤU.
2. KHÔNG BIẾN THÀNH CHATBOT HỎI ĐÁP THÔNG THƯỜNG:
   - TUYỆT ĐỐI HẠN CHẾ các câu hỏi chung chung rập khuôn chỉ để duy trì trò chuyện như: "Bạn cảm thấy thế nào?", "Tại sao bạn lại cảm thấy như vậy?", "Bạn có muốn chia sẻ thêm không?".
   - THAY VÀO ĐÓ: Phản ánh/nhận định dựa trên dữ liệu người dùng vừa cung cấp, sau đó mới đặt 1 câu hỏi trọng tâm để xác định nguyên nhân cụ thể.
3. NGUYÊN TẮC MỤC TIÊU DỮ LIỆU (Data-driven Inquiry):
   - Mỗi câu hỏi phải có mục đích thu thập dữ liệu cụ thể: Workload (khối lượng), Deadline (thời gian), Task-switching (đa nhiệm), Support (hỗ trợ), Autonomy (quyền chủ động), Recovery (phục hồi), hoặc Disengagement (xa rời công việc).
4. QUY TRÌNH SESSION KHÉP KÍN (Không hỏi lan man):
   - Khi người dùng đã nêu rõ nguyên nhân: Hãy phản ánh lại kết quả (ví dụ: "Tôi ghi nhận áp lực chính hôm nay đến từ deadline quá gần...") và đưa ra ngay 1 hành động hỗ trợ cụ thể (micro-action 5 phút).
   - Sau khi đã hỗ trợ: Tổng hợp nhận định và kết thúc phiên trò chuyện một cách trọn vẹn, không cố kéo dài cuộc hội thoại.
5. PHÂN TÁCH KHOA HỌC:
   - Trò chuyện nhằm bổ sung Bối cảnh/Giải thích (Context/Explanation), KHÔNG chẩn đoán bệnh lý y khoa và KHÔNG tự tiện tính điểm trực tiếp vào thang đo Burnout Core.
"""

import unicodedata

# Hotline banner - Fact-checked & verified information
CRISIS_HOTLINE_BANNER = """

---
🚨 **NẾU BẠN HOẶC NGƯỜI THÂN ĐANG GẶP NGUY HIỂM HOẶC CẦN HỖ TRỢ KHẨN CẤP:**
• 🚑 **115 — Cấp cứu Y tế Khẩn cấp Toàn quốc**: Hoạt động 24/7, miễn phí cước gọi từ mọi mạng viễn thông.
• 📞 **111 — Tổng đài Quốc gia Bảo vệ Trẻ em & Học sinh**: Hoạt động 24/7, miễn phí cước gọi.
• 📞 **096 306 1414 — Đường dây nóng "Ngày Mai" (Hỗ trợ Khủng hoảng Tâm lý & Trầm cảm)**: 13:00 – 20:30, Thứ Tư đến Chủ Nhật (tính cước viễn thông thông thường).
• 🏥 **Viện Sức khỏe Tâm thần — Bệnh viện Bạch Mai (Hà Nội)**: `024 3576 5344` / `096 798 1616` (Cấp cứu 24/7).
• 🏥 **Bệnh viện Tâm thần TP.HCM**: `1900 1267` / `028 3923 4675` (Cấp cứu 24/7).
*(Xin đừng ở một mình. Hãy kết nối ngay với người thân đáng tin cậy hoặc cơ sở y tế gần nhất).*"""

CRISIS_SAFETY_RESPONSE_TEMPLATE = (
    "Tôi cảm nhận được bạn đang phải trải qua một thời điểm vô cùng khó khăn và cảm giác bế tắc quá lớn. "
    "Sự an toàn và sức khỏe của bạn là điều quan trọng nhất lúc này. "
    "Vì tôi là một trợ lý AI hỗ trợ tự nhận thức và không thể thay thế sự can thiệp y tế khẩn cấp, "
    "xin bạn hãy tạm dừng công việc, đừng ở một mình và kết nối ngay với người thân đáng tin cậy hoặc các đường dây nóng hỗ trợ chuyên nghiệp dưới đây:"
    + CRISIS_HOTLINE_BANNER
)

# Danh sách từ khóa nguy cơ tự hại (Có dấu & Không dấu)
CRISIS_CORE_SIGNALS = [
    "tự tử", "tu tu", "tự sát", "tu sat",
    "muốn chết", "muon chet", "không muốn sống", "khong muon song",
    "kết thúc cuộc sống", "ket thuc cuoc song", "kết thúc cuộc đời", "ket thuc cuoc doi",
    "chấm dứt cuộc sống", "cham dut cuoc song", "chấm dứt cuộc đời", "cham dut cuoc doi",
    "tự hại", "tu hai", "tự làm đau", "tu lam dau",
    "chết đi cho rồi", "chet di cho roi", "chết cho xong", "chet cho xong",
    "giải thoát cho xong", "giai thoat cho xong",
    "bế tắc hoàn toàn", "be tac hoan toan",
    "chán sống", "chan song", "không thiết sống", "khong thiet song",
    "muốn biến mất", "muon bien mat",
    "buông xuôi", "buong xuoi",
    "sống làm gì nữa", "song lam gi nua",
    "tồn tại làm gì", "ton tai lam gi",
]

# Các mẫu regex nhận diện ý niệm tự hại ngầm định (Passive Suicidal Ideation)
import re

PASSIVE_SUICIDE_PATTERNS = [
    re.compile(r"(không|chẳng|chả)\s+(bao giờ\s+)?(muốn\s+)?(phải\s+)?(tỉnh dậy|thức dậy)", re.IGNORECASE),
    re.compile(r"ngủ\s+(một giấc\s+)?(mãi\s+)?(không|chẳng)\s+(bao giờ\s+)?(dậy|tỉnh)", re.IGNORECASE),
    re.compile(r"(sống|tồn tại)\s+(để\s+)?làm\s+(gì|chi)\s+nữa", re.IGNORECASE),
    re.compile(r"ước\s+(gì\s+)?(mình\s+)?(chết|biến mất|không tồn tại|không tỉnh dậy|không thức dậy)", re.IGNORECASE),
    re.compile(r"chết\s+(đi\s+)?cho\s+(xong|rồi|rảnh)", re.IGNORECASE),
    re.compile(r"giải thoát\s+cho\s+(xong|bản thân)", re.IGNORECASE),
]

# Thành ngữ thông tục loại trừ (False positive whitelist)
COLLOQUIAL_EXCLUSIONS = [
    "mệt chết", "met chet", "đói chết", "doi chet", "cười chết", "cuoi chet",
    "sợ chết", "so chet", "chán chết", "chan chet", "chết tiệt", "chet tiet",
    "chết máy", "chet may", "chết nguồn", "chet nguon", "chết dở", "chet do",
    "chết cười", "chet cuoi", "nóng chết", "nong chet", "lạnh chết", "lanh chet",
    "buông xuôi tay lái", "buong xuoi tay lai",
]

# Cấu trúc phủ định (Negation check)
NEGATION_PATTERNS = [
    "không muốn chết", "khong muon chet",
    "chẳng muốn chết", "chang muon chet",
    "không có ý định tự tử", "khong co y dinh tu tu",
    "không tự tử", "khong tu tu",
    "không muốn tự sát", "khong muon tu sat",
    "không làm hại", "khong lam hai",
]


def strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để đối soát đa dạng cách gõ."""
    text_nfkd = unicodedata.normalize('NFKD', text)
    return ''.join([c for c in text_nfkd if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')


def evaluate_crisis_safety(message: str) -> tuple[bool, Optional[str]]:
    """Tiền kiểm duyệt an toàn khủng hoảng TRƯỚC KHI gọi LLM.

    Returns:
        (is_crisis, response_text_if_crisis)
    """
    if not message or not message.strip():
        return False, None

    msg_lower = message.lower().strip()
    msg_raw = strip_accents(msg_lower)

    # 1. Kiểm tra phủ định trước (ví dụ: 'tôi không muốn chết đâu')
    for neg in NEGATION_PATTERNS:
        if neg in msg_lower or neg in msg_raw:
            return False, None

    # 2. Kiểm tra thành ngữ thông tục (ví dụ: 'hôm nay mệt chết đi được')
    has_colloquial = False
    for coll in COLLOQUIAL_EXCLUSIONS:
        if coll in msg_lower or coll in msg_raw:
            has_colloquial = True
            break

    # 3. Quét tín hiệu nguy cơ bằng từ khóa
    has_crisis_signal = False
    for sig in CRISIS_CORE_SIGNALS:
        if sig in msg_lower or sig in msg_raw:
            has_crisis_signal = True
            break

    # 4. Quét tín hiệu nguy cơ bằng Regex (Passive suicidal patterns)
    if not has_crisis_signal:
        for pat in PASSIVE_SUICIDE_PATTERNS:
            if pat.search(msg_lower) or pat.search(msg_raw):
                has_crisis_signal = True
                break

    # Nếu chỉ có thành ngữ thông tục mà không có tín hiệu nguy hại nghiêm trọng rõ rệt -> Không phải crisis
    if has_colloquial and not any(k in msg_lower or k in msg_raw for k in ["tự tử", "tu tu", "tự sát", "tu sat", "muốn chết", "muon chet"]):
        return False, None

    if has_crisis_signal and not has_colloquial:
        logger.warning("CRISIS SAFETY INTERLOCK ACTIVATED for message: %s", message[:50])
        return True, CRISIS_SAFETY_RESPONSE_TEMPLATE

    return False, None



@dataclass
class ChatAnalysisContext:
    """Context từ AI analysis của message."""
    stress_score: float
    burnout_score: float
    fatigue_score: float
    detected_signals: List[str]
    keywords: List[str]
    sentiment: str
    face_emotion: Optional[dict] = None  # Multimodal: Dữ liệu cảm xúc khuôn mặt từ DeepFace


@dataclass
class ChatResponse:
    """Response từ AI chat generator."""
    content: str
    analysis_context: Optional[ChatAnalysisContext]
    follow_up_topic: Optional[str]
    is_fallback: bool = False
    finish_reason: Optional[str] = None


class ChatResponseGenerator:
    """Generate AI-powered responses for emotion chat."""

    def __init__(self, gemini_service=None):
        self._gemini = gemini_service

    def _get_gemini(self):
        """Lazy load Google GenAI client."""
        if self._gemini is None:
            try:
                from google import genai
                from app.core.settings import get_settings
                settings = get_settings().google_ai
                if settings.api_key:
                    self._gemini = genai.Client(api_key=settings.api_key)
            except Exception as e:
                logger.error("Failed to init genai client in ChatResponseGenerator: %s", e)
        return self._gemini

    # Q-A: Các stage hợp lệ mà route có thể truyền vào.
    # Generator KHÔNG tự quyết stage — đây là single source of truth principle (B1).
    VALID_STAGES = frozenset({
        "greeting_and_probe",
        "clarifying_cause",
        "reflect_and_support",
        "wrapping_up",
        "crisis_support",
    })

    # Q-B: 2 stage cấm hỏi (không được có dấu ? ở response).
    FORBIDDEN_QUESTION_STAGES = frozenset({
        "reflect_and_support",
        "wrapping_up",
    })

    def generate_response(
        self,
        user_message: str,
        stage: str,                                # BẮT BUỘC từ route (B1)
        analysis_context: Optional[ChatAnalysisContext] = None,
        conversation_history: List[dict] = None,
        survey_context: Optional[dict] = None,
        session_id: Optional[str] = None,
        assessment_id: Optional[str] = None,
        primary_cause: Optional[str] = None,       # Cho fallback stage-aware (Q4)
        micro_action: Optional[str] = None,
        message_count: int = 0,                    # Chỉ dùng cho no-greeting rule
    ) -> ChatResponse:
        """Generate a natural, empathetic response.

        B1: stage BẮT BUỘC — generator không tự suy ra từ message_count.
            Đây là single source of truth principle: route quyết stage,
            generator chỉ thực thi.

        GAP-7: evaluate_crisis_safety đã được route chặn trước. Generator
            KHÔNG gọi lại để tránh logic phân tán.

        Args:
            user_message: Tin nhắn mới của user.
            stage: Tên stage đã được route quyết định.
            analysis_context: KHÔNG dùng trong luồng chat nữa (Q1: bỏ inline analyze).
                Tham số giữ để tương thích ngược với test/Caller cũ.
            survey_context: Dữ liệu khảo sát gần nhất (cho prompt greeting).
            session_id: Firestore session ID cho probing_service.
            primary_cause, micro_action: Đã được route ghi lên session, dùng
                cho fallback stage-aware nếu Gemini fail.
        """
        if stage not in self.VALID_STAGES:
            raise ValueError(
                f"Invalid stage: {stage!r}. Must be one of {sorted(self.VALID_STAGES)}"
            )

        # PR 2 (Test 9): Detect user muốn dừng → trả fallback nhẹ, KHÔNG gọi Gemini
        from app.modules.chat.services.probing_questions import get_probing_questions_service
        probing_service = get_probing_questions_service()
        if probing_service.detect_user_wants_to_stop(user_message):
            logger.info("User wants to stop. Returning gentle fallback without Gemini call.")
            stop_response = (
                "Tôi tôn trọng quyết định của bạn. Cảm ơn bạn đã dành thời gian chia sẻ. "
                "Khi nào bạn muốn quay lại, tôi luôn ở đây nhé."
            )
            return ChatResponse(
                content=stop_response,
                analysis_context=analysis_context,
                follow_up_topic=None,
                is_fallback=True,
                finish_reason="USER_STOPPED",
            )

        history_text = self._build_history_text(conversation_history or [])
        # XÓA: stage = self._determine_stage(message_count) — sửa BUG-01, GAP-1
        prompt, cached_probe = self._build_prompt(
            user_message=user_message,
            history_text=history_text,
            analysis_summary="",  # Q1: bỏ analysis block
            stage=stage,
            survey_context=survey_context,
            message_count=message_count,
            session_id=session_id,
            assessment_id=assessment_id,
        )

        try:
            response_text, finish_reason = self._generate_with_gemini(prompt)

            # Q-B: Post-validation — nếu stage cấm hỏi mà output có '?',
            # thay bằng fallback stage-aware. KHÔNG cắt chuỗi.
            if self._output_violates_stage(response_text, stage):
                logger.info(
                    "Output violates stage=%s (contains '?' in forbidden stage). "
                    "Replacing with stage-aware fallback.",
                    stage,
                )
                response_text = self._stage_aware_fallback(
                    stage=stage,
                    survey_context=survey_context,
                    primary_cause=primary_cause,
                    micro_action=micro_action,
                )
                finish_reason = finish_reason + "_STAGE_VIOLATION"

            return ChatResponse(
                content=response_text,
                analysis_context=analysis_context,
                follow_up_topic=cached_probe.topic if cached_probe else self._extract_follow_up_topic(response_text),
                is_fallback=False,
                finish_reason=finish_reason,
            )
        except Exception as exc:
            logger.error("Failed to generate chat response: %s", exc)
            # Q-C: fallback theo stage, KHÔNG theo ctx.sentiment
            fallback_text = self._stage_aware_fallback(
                stage=stage,
                survey_context=survey_context,
                primary_cause=primary_cause,
                micro_action=micro_action,
            )
            return ChatResponse(
                content=fallback_text,
                analysis_context=analysis_context,
                follow_up_topic=None,
                is_fallback=True,
                finish_reason="FALLBACK",
            )

    def _output_violates_stage(self, text: str, stage: str) -> bool:
        """Q-B: Heuristic bảo thủ phát hiện output có câu hỏi ở 2 stage cấm hỏi.

        Version 1: chỉ check ký tự ASCII '?'. Đơn giản, có test false positive
        cho câu tu từ không có dấu '?'. False negative được chấp nhận ở v1
        (xem test_sta_chat_v2_1_fallback.py).
        """
        if stage not in self.FORBIDDEN_QUESTION_STAGES:
            return False
        return "?" in (text or "")

    def _stage_aware_fallback(
        self,
        stage: str,
        survey_context: Optional[dict] = None,
        primary_cause: Optional[str] = None,
        micro_action: Optional[str] = None,
    ) -> str:
        """Q-C: Fallback deterministic theo stage, KHÔNG hỏi ở 2 stage cuối.

        Nguyên tắc:
        - greeting_and_probe: phản ánh data đã được xác thực (survey), hỏi 1 câu trọng tâm.
        - clarifying_cause: hỏi ngắn, không áp lực.
        - reflect_and_support: CHỈ phản ánh nguyên nhân nếu primary_cause đã ghi.
          Nếu thiếu → câu trung tính, KHÔNG hỏi.
        - wrapping_up: tổng kết trung tính, KHÔNG gán nguyên nhân, KHÔNG hỏi.
        - crisis_support: giữ CRISIS_SAFETY_RESPONSE_TEMPLATE.
        """
        if stage == "crisis_support":
            return CRISIS_SAFETY_RESPONSE_TEMPLATE

        if stage == "greeting_and_probe":
            reasons_list = (survey_context or {}).get("overload_reasons", [])
            if reasons_list:
                reasons_str = ", ".join(reasons_list)
                return (
                    f"Qua khảo sát gần nhất, tôi nhận thấy bạn đang chịu áp lực từ {reasons_str}. "
                    "Điều gì trong công việc tạo áp lực lớn nhất cho bạn hôm nay?"
                )
            return (
                "Qua thông tin ghi nhận ban đầu, tôi nhận thấy bạn đang gặp nhiều căng thẳng trong công việc. "
                "Điều gì đang tạo áp lực lớn nhất cho bạn hôm nay?"
            )

        if stage == "clarifying_cause":
            return "Bạn có thể chia sẻ thêm một điều khiến bạn bận tâm nhất lúc này không?"

        if stage == "reflect_and_support":
            # Chỉ phản ánh khi CẢ primary_cause VÀ micro_action đều có sẵn
            if primary_cause and micro_action:
                return (
                    f"Tôi ghi nhận bạn đã chia sẻ về vấn đề {primary_cause}. "
                    f"Trong 5 phút tới, bạn có thể thử: {micro_action}. "
                    "Hãy thử khi bạn sẵn sàng."
                )
            # Fallback trung tính, KHÔNG hỏi
            return (
                "Tôi ghi nhận những chia sẻ của bạn. "
                "Hãy dành ít phút nghỉ ngơi và quay lại khi bạn sẵn sàng nhé."
            )

        if stage == "wrapping_up":
            # Tổng kết trung tính — KHÔNG gán nguyên nhân cụ thể
            return (
                "Cảm ơn bạn đã dành thời gian chia sẻ. "
                "Hãy nghỉ ngơi và chăm sóc bản thân nhé. Hẹn gặp lại bạn."
            )

        # Stage không xác định → fallback an toàn, không hỏi
        return "Cảm ơn bạn đã chia sẻ. Hãy nghỉ ngơi nhé."

    def _build_history_text(self, history: List[dict]) -> str:
        """Build readable history text for prompt."""
        if not history:
            return "Chưa có lịch sử trò chuyện."

        lines = []
        for msg in history[-6:]:
            role = "Người dùng" if msg.get("role") == "user" else "Tư vấn viên"
            content = msg.get("content", "")[:200]
            lines.append(role + ": " + content)

        return "\n".join(lines)

    def _build_analysis_summary(self, ctx: ChatAnalysisContext) -> str:
        """Build analysis summary for prompt."""
        parts = [
            "- Mức stress: " + str(int(ctx.stress_score)) + "/100",
            "- Tín hiệu burnout: " + str(int(ctx.burnout_score)) + "/100",
            "- Mệt mỏi: " + str(int(ctx.fatigue_score)) + "/100",
        ]

        if ctx.face_emotion:
            dominant = ctx.face_emotion.get("dominant_emotion", "Unknown")
            conf = ctx.face_emotion.get("confidence", 0.0)
            parts.append(
                f"- Cảm xúc khuôn mặt webcam (DeepFace): {dominant} (Độ tin cậy: {int(conf * 100)}%). Hãy thể hiện sự thấu cảm tinh tế đối với trạng thái khuôn mặt này."
            )

        if ctx.detected_signals:
            signals_str = ", ".join(ctx.detected_signals[:5])
            parts.append("- Tín hiệu phát hiện: " + signals_str)

        if ctx.keywords:
            keywords_str = ", ".join(ctx.keywords[:10])
            parts.append("- Từ khóa: " + keywords_str)

        parts.append("- Cảm xúc: " + ctx.sentiment)

        return "\n".join(parts)

    def _build_prompt(
        self,
        user_message: str,
        history_text: str,
        analysis_summary: str,
        stage: str,
        survey_context: Optional[dict] = None,
        message_count: int = 1,
        session_id: Optional[str] = None,
        assessment_id: Optional[str] = None,
    ) -> tuple[str, Optional[Any]]:
        """Build full prompt for Gemini.

        Returns:
            tuple: (prompt_string, cached_probe) - cached_probe để route dùng ở
            Context Tagging mà không cần gọi lại probing_service.

        PR 1 (P0-02): Trích xuất FACTS user đã nói, đưa vào prompt.
        PR 2: Dùng select_micro_action() để micro-action theo context.
        PR 2: Dùng select_question_variant() để tránh lặp form câu hỏi.
        """
        from app.modules.chat.services.probing_questions import get_probing_questions_service
        probing_service = get_probing_questions_service()
        suggested_probe = probing_service.get_probing_question(
            user_message=user_message,
            survey_context=survey_context,
            session_id=session_id,
            assessment_id=assessment_id or "default",
        )

        # PR 1 (P0-02): Pre-extract facts từ user message
        facts_list = probing_service.extract_facts(user_message)
        facts_block = ""
        if facts_list:
            facts_lines = "\n".join(f"- {f}" for f in facts_list)
            facts_block = f"""
⚠️ FACTS NGƯỜI DÙNG ĐÃ NÊU TRONG TIN NHẮN NÀY (BẮT BUỘC phản ánh trước khi hỏi):
{facts_lines}
→ TUYỆT ĐỐI KHÔNG hỏi lại những thông tin đã có ở trên.
→ CÂU HỎI (nếu có) phải ĐÀO SÂU thêm: tác động, cảm xúc, hoặc nguyên nhân gốc.
"""

        # PR 2: Chọn biến thể câu hỏi (tránh lặp form)
        if suggested_probe:
            question_text = probing_service.select_question_variant(
                suggested_probe, user_message, history_text
            )
            # PR 2: Chọn micro-action theo context (user đã thử → đổi action)
            micro_action_text = probing_service.select_micro_action(
                suggested_probe, user_message, facts_list
            )
        else:
            question_text = "Điều gì trong công việc đang tạo áp lực lớn nhất cho bạn hôm nay?"
            micro_action_text = "Dành 5 phút tạm hoãn 1 việc chưa khẩn cấp và hít thở sâu để cân bằng lại."

        stage_instruction = {
            "greeting_and_probe": (
                "GIAI ĐOẠN 1 - GHI NHẬN & ĐẶT CÂU HỎI TRỌNG TÂM: "
                "Chào hỏi ấm áp, phản ánh nhận định dựa trên dữ liệu người dùng vừa cung cấp trong khảo sát. "
                f"ĐẶT DUY NHẤT 1 CÂU HỎI TRỌNG TÂM ĐỂ XÁC ĐỊNH NGUYÊN NHÂN: '{question_text}'."
            ),
            "clarifying_cause": (
                "GIAI ĐOẠN 2 - XÁC ĐỊNH RÕ NGUYÊN NHÂN: "
                "Lắng nghe câu trả lời của người dùng. Trích dẫn lại chính xác nguyên nhân họ vừa chia sẻ "
                "(Ví dụ: deadline sát nút, phải làm nhiều việc cùng lúc, hoặc thiếu người hỗ trợ). "
                "Hỏi thêm 1 câu ngắn để xác định tác động chính đến sự tập trung hoặc khả năng hồi phục của họ."
            ),
            "reflect_and_support": (
                "GIAI ĐOẠN 3 - PHẢN ÁNH & HỖ TRỢ: "
                "1. Phản ánh ngắn nguyên nhân user vừa nói (1-2 câu). "
                f"2. Đưa ra DUY NHẤT 1 micro-action 5 phút khả thi: '{micro_action_text}'. "
                "🚫 CẤM TUYỆT ĐỐI: KHÔNG được đặt bất kỳ câu hỏi nào (kể cả tu từ). "
                "KHÔNG kết thúc bằng dấu '?'. Nếu bạn đặt câu hỏi, output sẽ bị backend từ chối và thay bằng câu trung tính."
            ),
            "wrapping_up": (
                "GIAI ĐOẠN 4 - TỔNG KẾT & KẾT THÚC: "
                "Tóm tắt 1-2 điểm cốt lõi, dặn dò ấm áp, chào tạm biệt. "
                "🚫 CẤM TUYỆT ĐỐI: KHÔNG mở chủ đề mới, KHÔNG đặt câu hỏi. "
                "KHÔNG kết thúc bằng dấu '?'. Output vi phạm sẽ bị backend thay bằng câu tổng kết trung tính."
            ),
            "crisis_support": (
                "GIAI ĐOẠN KHẨN CẤP - AN TOÀN: "
                "Không gọi Gemini. Backend sẽ trả về CRISIS_SAFETY_RESPONSE_TEMPLATE tự động."
            ),
        }

        survey_block = ""
        if survey_context:
            job_title = survey_context.get("job_title", "Chuyên viên")
            industry_name = survey_context.get("industry_name", "Văn phòng")
            archetype_name = survey_context.get("archetype_name", "")
            reflection_q = survey_context.get("reflection_question", "")
            reasons = ", ".join(survey_context.get("overload_reasons", [])) or "áp lực công việc thông thường"
            sleep_h = survey_context.get("sleep_hours", 7)
            rec_s = survey_context.get("recovery_score", 3)

            survey_block = f"""
BỐI CẢNH NGHỀ NGHIỆP & KẾT QUẢ KHẢO SÁT GẦN NHẤT CỦA NGƯỜI DÙNG:
- Vị trí / Lĩnh vực: {job_title} ({industry_name})
- Hình mẫu năng lượng đo lường: {archetype_name}
- Thể trạng gần nhất: Giấc ngủ {sleep_h}h, Điểm hồi phục buổi sáng: {rec_s}/5
- Lý do quá tải ghi nhận: {reasons}
- Câu hỏi gợi mở suy ngẫm vừa gửi cho người dùng: "{reflection_q}"
* CHỈ DẪN CHUYỂN TIẾP QUAN TRỌNG: Người dùng đang chuyển tiếp trực tiếp từ kết quả khảo sát sang trò chuyện cùng bạn. Bạn ĐÃ BIẾT toàn bộ thông tin này, hãy phản hồi tự nhiên, thấu hiểu đúng chuyên môn ngành nghề của họ và TUYỆT ĐỐI KHÔNG hỏi lại những thông tin người dùng đã cung cấp ở trên!
"""

        no_greeting_rule = ""
        if message_count >= 2:
            no_greeting_rule = (
                f"- BẮT BUỘC: Đây là lượt trao đổi tiếp nối (lượt thứ {message_count}). "
                "TUYỆT ĐỐI KHÔNG chào hỏi lại ('Chào bạn', 'Xin chào', v.v.). "
                "Đi thẳng vào việc phản hồi cảm xúc, đồng cảm và phân tích nội dung người dùng vừa chia sẻ."
            )

        # STA Compact: block PHÂN TÍCH TÍN HIỆU TÂM LÝ chỉ chèn khi có data
        # (tránh prompt thừa, chat không tính điểm Burnout theo STA mục I.4)
        analysis_block = ""
        if analysis_summary and analysis_summary.strip():
            analysis_block = "PHÂN TÍCH TÍN HIỆU TÂM LÝ TỪ TIN NHẮN MỚI:\n" + analysis_summary + "\n\n"

        prompt = """Bạn là một chuyên gia tư vấn tâm lý chuyên nghiệp. Hãy LUÔN LUÔN trả lời bằng TIẾNG VIỆT CÓ DẤU CHUẨN XÁC 100%.

{}

{}
{}
GIAI ĐOẠN HỘI THOẠI HIỆN TẠI:
{}

LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY:
{}

{}TIN NHẮN MỚI CỦA NGƯỜI DÙNG: "{}"

YÊU CẦU PHẢN HỒI:
- BẮT BUỘC viết bằng tiếng Việt có dấu chuẩn xác 100%, tự nhiên, thấu cảm.
- Độ dài dưới 180 từ.
{}
- Phản ánh dựa trên dữ liệu người dùng vừa chia sẻ, không hỏi các câu sáo rỗng vô thưởng vô phạt.
- Tuân thủ chỉ dẫn giai đoạn hội thoại ở trên.
"""
        return prompt.format(
            SYSTEM_PROMPT,
            survey_block,
            facts_block,
            stage_instruction.get(stage, stage),
            history_text,
            analysis_summary,
            user_message,
            no_greeting_rule,
        ), suggested_probe  # PR 2: trả về probe để cache

    def _generate_with_gemini(self, prompt: str) -> tuple[str, str]:
        """Generate response using Gemini with safety interlock, smart retry, key rotation, and multi-model fallback.

        Returns:
            tuple[str, str]: (response_text, finish_reason_str)
        """
        from app.core.gemini_rotator import get_gemini_rotator
        from google.genai import types

        rotator = get_gemini_rotator()

        primary_config = types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=1500,
            thinking_config=types.ThinkingConfig(thinking_budget=512),
        )

        def _call_gemini(client, model):
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=primary_config,
            )

        response, model_used, key_used = rotator.execute_with_failover(_call_gemini)

        if not response or not response.candidates:
            raise RuntimeError("Gemini returned no candidates")

        candidate = response.candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)
        finish_reason_str = str(finish_reason) if finish_reason else "UNKNOWN"

        # Cấu hình 2A: Tự động retry thông minh 1 lần nếu chạm trần MAX_TOKENS
        if "MAX_TOKENS" in finish_reason_str:
            logger.warning(
                "Gemini response hit MAX_TOKENS limit (%s). Triggering smart retry with zero-thinking to recover full text...",
                finish_reason_str,
            )
            recovery_config = types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1500,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            client = rotator._get_client_for_key(key_used)
            retry_resp = client.models.generate_content(
                model=model_used,
                contents=prompt,
                config=recovery_config,
            )
            if retry_resp and retry_resp.candidates:
                candidate = retry_resp.candidates[0]
                rec_finish = getattr(candidate, "finish_reason", None)
                finish_reason_str = str(rec_finish) if rec_finish else "STOP"
                logger.info("Smart retry succeeded. Recovered finish_reason: %s", finish_reason_str)
                if hasattr(retry_resp, "text") and retry_resp.text:
                    return retry_resp.text.strip(), finish_reason_str

        # Kiểm tra nếu bị bộ lọc an toàn chặn
        if "SAFETY" in finish_reason_str:
            logger.warning("Gemini response blocked by safety filter: %s", finish_reason_str)
            raise RuntimeError("Gemini response blocked by safety filter")

        if hasattr(response, "text") and response.text:
            return response.text.strip(), finish_reason_str

        raise RuntimeError("Empty response text from Gemini")

    def _extract_follow_up_topic(self, response: str) -> Optional[str]:
        """Extract topic for follow-up from response."""
        if "?" in response:
            for sentence in response.split("."):
                if "?" in sentence:
                    return sentence.strip()[:100]
        return None

    def _generate_fallback_response(self, ctx: Optional[ChatAnalysisContext], user_message: str = "") -> ChatResponse:
        """Generate dynamic fallback response if AI fails."""
        ctx = ctx or ChatAnalysisContext(
            stress_score=0, burnout_score=0, fatigue_score=0,
            detected_signals=[], keywords=[], sentiment="neutral",
        )
    # BUG-04 / Q-C: _generate_fallback_response cũ đã được thay thế bằng
    # _stage_aware_fallback (xem ở generate_response). Method này XÓA trong v2.1
    # vì trộn sentiment analysis với stage, vi phạm STA.


# Singleton
_generator: Optional[ChatResponseGenerator] = None


def get_chat_response_generator() -> ChatResponseGenerator:
    """Get singleton instance."""
    global _generator
    if _generator is None:
        _generator = ChatResponseGenerator()
    return _generator
