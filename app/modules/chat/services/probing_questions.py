"""
==============================================================
File: probing_questions.py

ProbingQuestionsService - Bộ câu hỏi trọng tâm đào sâu nguyên nhân theo chuẩn STA.
Nguyên tắc:
- 100% Tiếng Việt có dấu chuẩn xác.
- Mỗi câu hỏi phải có mục đích lấy dữ liệu cụ thể (Workload, Deadline, Task-switching, Support, Control, Recovery, Disengagement).
- Không hỏi chung chung để duy trì hội thoại.

PR 1 (P0-01): Thêm rule-based negation handling.
- Từ phủ định ('không', 'chẳng', 'chả', 'chưa', 'đừng') trong phạm vi 4 tokens
  trước keyword sẽ LOẠI BỎ topic tương ứng khỏi danh sách ứng viên.
- Xử lý an toàn, deterministic, không tốn Gemini call.
==============================================================
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from app.modules.chat.repositories.chat_session_repository import ChatSessionRepository


# PR 1 (P0-01): Từ điển phủ định dùng cho negation handling.
# Khi một trong các từ này xuất hiện trong vùng 4-tokens trước keyword,
# keyword đó bị coi là phủ định và KHÔNG match topic.
NEGATION_WORDS: Set[str] = frozenset({
    "không", "khong", "chẳng", "chang", "chả", "cha",
    "chưa", "chua", "đừng", "đung", "đừng", "dung",
    "không phải", "khong phai", "chẳng phải", "chang phai",
    "không có", "khong co", "chẳng có", "chang co",
    "không hề", "khong he", "chẳng hề", "chang he",
})


@dataclass
class ProbingQuestion:
    """Câu hỏi trọng tâm đào sâu nguyên nhân.

    PR 2: Mở rộng với:
    - question_variants: 2-3 biến thể câu hỏi để tránh lặp lại cùng 1 form.
    - micro_action_conditional: dict {condition: action}. Action được chọn
      dựa trên context (user đã thử gì, có fact nào, ...). Nếu không match
      condition nào → dùng micro_action mặc định.
    """
    topic: str
    target_dimension: str
    data_objective: str
    question: str
    reflection_template: str
    micro_action: str
    keywords: List[str]
    # PR 2 fields
    question_variants: List[str] = None  # type: ignore[assignment]
    micro_action_conditional: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.question_variants is None:
            self.question_variants = []
        if self.micro_action_conditional is None:
            self.micro_action_conditional = {}


# Bộ 7 nhóm câu hỏi chuẩn theo tài liệu STA
# PR 2: Mỗi topic có thêm question_variants (2-3 biến thể) + micro_action_conditional
# (action theo context). Nếu context match → dùng action điều kiện, nếu không → mặc định.
STA_QUESTION_CATALOG: Dict[str, ProbingQuestion] = {
    "workload": ProbingQuestion(
        topic="workload",
        target_dimension="Khối lượng công việc (Workload)",
        data_objective="Xác định nguyên nhân quá tải do số lượng đầu việc hay lý do phát sinh khác",
        question="Tôi nhận thấy khối lượng công việc hôm nay đang khá cao. Điều khiến bạn quá tải chủ yếu là số lượng việc quá nhiều hay còn nguyên nhân nào khác?",
        reflection_template="Tôi ghi nhận rằng khối lượng công việc dồn dập đang là yếu tố chính tạo áp lực cho bạn hôm nay.",
        micro_action="Trong 5 phút tới, bạn có thể rà soát danh sách việc và tạm gác lại 1 đầu việc chưa thực sự khẩn cấp để giảm tải ngay lập tức.",
        keywords=["quá tải", "nhiều việc", "khối lượng", "dồn việc", "ôm việc", "om viec", "qua tai", "nhieu viec"],
        question_variants=[
            "Bạn đang quá tải. Trong số các đầu việc hôm nay, việc nào chiếm nhiều thời gian nhất?",
            "Khối lượng công việc lớn đến mức nào - bạn có thể ước lượng bao nhiêu giờ mỗi ngày cho việc ngoài kế hoạch?",
        ],
        micro_action_conditional={
            "user_tried_already": "Có vẻ bạn đã thử giảm tải trước đó. Trước khi nghĩ thêm giải pháp cá nhân, bạn có thể cùng quản lý thống nhất tiêu chí ưu tiên rõ ràng hơn.",
            "team_shortage": "Với tình trạng nhóm thiếu người, bạn có thể đề xuất hoãn một số đầu việc chưa thực sự gấp để bảo vệ chất lượng phần việc còn lại.",
        },
    ),
    "deadline": ProbingQuestion(
        topic="deadline",
        target_dimension="Áp lực thời gian / Deadline (Time Pressure)",
        data_objective="Phân biệt áp lực do deadline sát nút hay do mật độ việc dồn trong cùng khung giờ",
        question="Có vẻ áp lực thời gian đang ảnh hưởng khá rõ đến bạn. Hiện tại vấn đề chính là deadline quá gần hay bạn phải hoàn thành quá nhiều việc trong cùng một khoảng thời gian?",
        reflection_template="Tôi ghi nhận rằng áp lực chính của bạn hôm nay đến từ thời hạn gấp rút và nhiều đầu việc dồn trong cùng khung giờ.",
        micro_action="Hãy chọn ra duy nhất 1 việc có deadline gần nhất để giải quyết trước trong 25 phút tới, tạm tắt thông báo các việc còn lại.",
        keywords=["deadline", "gấp", "hạn chót", "sát nút", "chạy tiến độ", "không kịp", "khong kip", "ap luc thoi gian"],
        question_variants=[
            "Deadline nào đang 'đè' nặng nhất lên bạn lúc này?",
            "Bạn có thể chia sẻ deadline cụ thể nào đang khiến bạn áp lực nhất?",
        ],
        micro_action_conditional={
            "user_tried_already": "Nếu bạn đã ưu tiên rồi mà vẫn quá tải, có thể đây là lúc cần nói rõ với quản lý rằng 1 deadline cần dời lại - điều đó không phải né tránh mà là bảo vệ chất lượng.",
        },
    ),
    "task_switching": ProbingQuestion(
        topic="task_switching",
        target_dimension="Đa nhiệm / Chuyển ngữ cảnh (Task Switching)",
        data_objective="Xác định việc nhảy task liên tục gây khó tập trung hay mệt mỏi tinh thần",
        question="Tôi nhận thấy hôm nay bạn phải chuyển đổi giữa khá nhiều công việc. Việc này đang khiến bạn khó tập trung hay làm bạn cảm thấy mệt mỏi hơn?",
        reflection_template="Tôi nhận thấy việc chuyển đổi liên tục giữa nhiều đầu việc đang tiêu hao đáng kể khả năng tập trung và năng lượng của bạn.",
        micro_action="Bạn có thể thử nhóm các việc nhỏ tương tự vào một khung giờ cố định thay vì xử lý xen kẽ ngắt quãng.",
        keywords=["nhiều việc cùng lúc", "nhảy việc", "loạn việc", "ngắt quãng", "phân tâm", "khó tập trung", "chuyen task", "task switching"],
        question_variants=[
            "Trong 1 giờ qua bạn phải chuyển qua bao nhiêu việc khác nhau?",
            "Việc bị ngắt quãng thường đến từ đâu - email, đồng nghiệp nhờ, hay hệ thống?",
        ],
        micro_action_conditional={
            "user_tried_already": "Bạn đã cố gắng rồi. Có thể cần thống nhất với team một 'giờ vào sâu' (deep work) mà không ai ngắt quãng - đó là giải pháp cấp nhóm, không phải cá nhân.",
        },
    ),
    "support": ProbingQuestion(
        topic="support",
        target_dimension="Nguồn lực hỗ trợ (Community / Support)",
        data_objective="Xác định nguồn lực thiếu hụt từ đồng nghiệp, quản lý hay công cụ/nguồn lực",
        question="Tôi nhận thấy bạn đang gặp khá nhiều áp lực trong công việc. Bạn đang thiếu sự hỗ trợ chủ yếu từ đồng nghiệp, quản lý hay nguồn lực để hoàn thành công việc?",
        reflection_template="Tôi ghi nhận rằng cảm giác thiếu sự phối hợp và hỗ trợ kịp thời đang làm tăng gánh nặng của bạn.",
        micro_action="Hãy ghi lại 1 điểm nghẽn cụ thể nhất cần trợ giúp để trao đổi thẳng thắn và ngắn gọn với đồng nghiệp hoặc quản lý.",
        keywords=["thiếu hỗ trợ", "một mình", "không ai giúp", "cô lập", "quản lý", "đồng nghiệp", "thieu ho tro", "mot minh"],
        question_variants=[
            "Bạn cần hỗ trợ từ ai nhất lúc này - đồng nghiệp, quản lý, hay thiếu công cụ/thông tin?",
        ],
        micro_action_conditional={},  # Không ép action nếu user vừa phủ nhận thiếu support
    ),
    "autonomy": ProbingQuestion(
        topic="autonomy",
        target_dimension="Quyền chủ động (Control / Autonomy)",
        data_objective="Xác định rào cản do phụ thuộc quyết định người khác hay quy trình cứng nhắc",
        question="Có vẻ bạn đang gặp khó khăn trong việc chủ động xử lý công việc. Vấn đề nằm ở việc bạn phải phụ thuộc vào quyết định của người khác hay quy trình công việc hiện tại?",
        reflection_template="Tôi nhận thấy sự phụ thuộc vào phê duyệt và quy trình đang làm hạn chế quyền tự chủ và tạo thêm sự bức bối cho bạn.",
        micro_action="Bạn hãy tập trung vào phần việc nằm hoàn toàn trong tầm kiểm soát của mình trước, tạm buông phần đang phải chờ người khác duyệt.",
        keywords=["không được quyết", "chờ duyệt", "phụ thuộc", "quy trình", "bị động", "không chủ động", "cho duyet", "bi dong"],
        question_variants=[
            "Phần việc nào bạn hoàn toàn có thể quyết được mà không cần chờ ai?",
        ],
        micro_action_conditional={},
    ),
    "recovery": ProbingQuestion(
        topic="recovery",
        target_dimension="Phục hồi năng lượng (Recovery / Detachment)",
        data_objective="Phân biệt do dư âm công việc xâm lấn sau giờ làm hay do thiếu thời gian nghỉ ngơi",
        question="Tôi nhận thấy bạn đang khó lấy lại năng lượng sau giờ làm. Điều này chủ yếu do công việc vẫn tiếp tục ảnh hưởng đến bạn sau giờ làm hay do bạn chưa có đủ thời gian nghỉ ngơi?",
        reflection_template="Tôi ghi nhận rằng cơ thể và tâm trí bạn đang gặp khó khăn trong việc 'tắt nguồn' và ngắt kết nối sau ngày làm việc.",
        micro_action="Tối nay, hãy dành ít nhất 30 phút trước khi ngủ ngắt toàn bộ thông báo công việc để hệ thần kinh được nghỉ ngơi thực sự.",
        keywords=["mệt", "không hồi phục", "uể oải", "khó ngủ", "mất ngủ", "thức khuya", "chưa hồi sức", "met moi", "kho ngu"],
        question_variants=[
            "Bạn có thường xuyên nghĩ về công việc ngay cả khi đã tan làm?",
        ],
        micro_action_conditional={
            "user_tried_already": "Nếu bạn đã cố gắng 'tắt nguồn' rồi mà vẫn khó ngủ, có thể cần xem xét mức độ quá tải đang ăn mòn giấc ngủ - nguồn gốc có thể nằm ở khối lượng việc, không chỉ thói quen cá nhân.",
        },
    ),
    "disengagement": ProbingQuestion(
        topic="disengagement",
        target_dimension="Mất kết nối / Xa cách công việc (Disengagement)",
        data_objective="Xác định nguyên nhân mất kết nối do kiệt sức, mất ý nghĩa hay bất mãn môi trường",
        question="Gần đây bạn có vẻ ít muốn tiếp xúc với công việc hơn trước. Điều này chủ yếu đến từ sự mệt mỏi, cảm giác công việc không còn ý nghĩa hay một vấn đề nào khác?",
        reflection_template="Tôi nhận thấy sự xa rời và giảm sút động lực hiện tại là tín hiệu bảo vệ tự nhiên của tâm trí khi đối mặt với sự quá tải kéo dài.",
        micro_action="Hãy cho phép bản thân nghỉ ngơi ngắn và nhớ rằng giá trị bản thân không chỉ định nghĩa bằng năng suất của một ngày làm việc.",
        keywords=["chán", "không muốn làm", "bất cần", "vô nghĩa", "muốn nghỉ", "tránh né", "mat ket noi", "chan viec"],
        question_variants=[
            "Có điều gì trong công việc trước đây từng có ý nghĩa với bạn mà giờ không còn nữa?",
        ],
        micro_action_conditional={},
    ),
}


class ProbingQuestionsService:
    """Service tạo câu hỏi trọng tâm STA theo dữ liệu khảo sát và tin nhắn.

    State (used_topics) đọc/ghi qua ChatSessionRepository → Firestore, đảm bảo
    đồng bộ giữa các gunicorn worker.
    """

    def __init__(self, session_repo: Optional["ChatSessionRepository"] = None):
        # Lazy import để tránh circular dependency
        if session_repo is None:
            from app.modules.chat.repositories.chat_session_repository import (
                get_chat_session_repository,
            )
            session_repo = get_chat_session_repository()
        self._session_repo = session_repo

    def get_probing_question(
        self,
        user_message: str,
        analysis_context: Optional[dict] = None,
        assessment_id: str = "default",
        survey_context: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> Optional[ProbingQuestion]:
        """Lấy câu hỏi trọng tâm phù hợp nhất theo dữ liệu bối cảnh.

        STA Compact: Ưu tiên user_message trước survey_context, vì phản ánh
        đúng nguyên nhân user vừa nêu thay vì ép theo khảo sát.

        Args:
            session_id: Bắt buộc để persist used_topics. Nếu None, used_topics
                sẽ là set rỗng (không đánh dấu được) — chỉ dùng cho lần đầu.
        """
        used_topics = self._get_used_topics(session_id) if session_id else set()

        # 1. Ưu tiên user_message (nếu user đã nói gì đó cụ thể)
        if user_message and user_message.strip():
            topic = self._detect_topic_from_text(user_message, used_topics)
            if topic and topic in STA_QUESTION_CATALOG:
                self._mark_used(session_id, topic, used_topics)
                return STA_QUESTION_CATALOG[topic]

        # 2. Fallback survey_context (chỉ khi user chưa nói, vd Turn 1)
        if survey_context:
            candidate = self._detect_topic_from_survey(survey_context, used_topics)
            if candidate:
                topic = candidate.topic
                self._mark_used(session_id, topic, used_topics)
                return candidate

        # 3. Fallback câu hỏi mặc định theo thứ tự ưu tiên
        return self._get_fallback_question(session_id, used_topics)

    def _detect_topic_from_survey(
        self, survey_context: dict, used_topics: set
    ) -> Optional[ProbingQuestion]:
        """Suy luận câu hỏi từ các chỉ số khảo sát bất thường."""
        reasons = [str(r).lower() for r in survey_context.get("overload_reasons", [])]
        reasons_text = " ".join(reasons)

        # Mapping theo lý do quá tải (Quick Overload reasons)
        if "thời gian" in reasons_text or "deadline" in reasons_text:
            if "deadline" not in used_topics:
                return STA_QUESTION_CATALOG["deadline"]

        if "nhiều việc cùng lúc" in reasons_text or "đa nhiệm" in reasons_text:
            if "task_switching" not in used_topics:
                return STA_QUESTION_CATALOG["task_switching"]

        if "quá nhiều việc" in reasons_text or "khối lượng" in reasons_text:
            if "workload" not in used_topics:
                return STA_QUESTION_CATALOG["workload"]

        if "hỗ trợ" in reasons_text:
            if "support" not in used_topics:
                return STA_QUESTION_CATALOG["support"]

        if "chủ động" in reasons_text:
            if "autonomy" not in used_topics:
                return STA_QUESTION_CATALOG["autonomy"]

        # Mapping theo điểm số hồi phục
        rec_score = survey_context.get("recovery_score")
        sleep_hours = survey_context.get("sleep_hours")
        if (rec_score is not None and rec_score <= 2) or (sleep_hours is not None and sleep_hours < 6.0):
            if "recovery" not in used_topics:
                return STA_QUESTION_CATALOG["recovery"]

        return None

    def _detect_topic_from_text(self, message: str, used_topics: set) -> Optional[str]:
        """Phát hiện chủ đề từ văn bản người dùng.

        PR 1 (P0-01): Có xử lý phủ định. Nguyên tắc:
        - Nếu MỘT keyword bất kỳ của topic bị phủ định → toàn bộ topic bị loại
          (giả định user nói về chủ đề này theo hướng phủ định, không nên hỏi tiếp).

        Ví dụ: "Tôi không thiếu hỗ trợ từ đồng nghiệp. Vấn đề là quản lý thay đổi
        yêu cầu liên tục." → 'hỗ trợ' bị phủ định → 'support' bị loại.
        """
        msg_lower = message.lower()
        best_topic = None
        max_matches = 0

        for topic, q_obj in STA_QUESTION_CATALOG.items():
            if topic in used_topics:
                continue
            # Nếu có bất kỳ keyword nào bị phủ định → loại cả topic
            has_negated_kw = any(
                kw in msg_lower and self._is_keyword_negated(msg_lower, kw)
                for kw in q_obj.keywords
            )
            if has_negated_kw:
                continue
            # Uu tien cac cum tu dai, dac thu hon (vi du 'nhieu viec cung luc' > 'nhieu viec')
            score = 0
            for kw in q_obj.keywords:
                if kw in msg_lower:
                    score += len(kw)
            if score > max_matches:
                max_matches = score
                best_topic = topic

        return best_topic

    @staticmethod
    def _is_keyword_negated(message_lower: str, keyword: str) -> bool:
        """Kiểm tra keyword có đang bị phủ định trong câu không.

        Quy tắc: Từ phủ định ('không', 'chẳng', 'chả', 'chưa', 'đừng', 'không phải')
        phải nằm trong phạm vi 8 từ TRƯỚC keyword (đủ rộng để bắt câu dài), và
        KHÔNG có dấu phẩy/dấu chấm ngăn cách (vì câu 'tôi không X, mà là Y' thì
        X bị phủ định nhưng Y không).

        Returns:
            True nếu keyword bị phủ định → loại khỏi match.
        """
        # Tìm TẤT CẢ vị trí keyword trong message
        pos = 0
        while True:
            idx = message_lower.find(keyword, pos)
            if idx == -1:
                break

            # Lấy phần văn bản trước keyword
            prefix = message_lower[:idx]
            # Loại bỏ phần sau dấu phẩy/chấm gần nhất (reset scope)
            for sep in [",", ".", ";", "!", "?", " nhưng ", " mà "]:
                sep_idx = prefix.rfind(sep)
                if sep_idx != -1:
                    prefix = prefix[sep_idx + 1:]
                    break
            tokens_before = prefix.split()

            # Check 8 token gần nhất trước keyword
            window = tokens_before[-8:] if len(tokens_before) >= 8 else tokens_before
            for tok in window:
                # Tách token sạch (loại bỏ dấu câu dính)
                clean = tok.strip(".,;:!?\"'()")
                if clean in NEGATION_WORDS:
                    return True

            pos = idx + len(keyword)
        return False

    def extract_facts(self, message: str) -> List[str]:
        """Trích xuất các fact cụ thể từ user message (PR 1 - P0-02).

        Dùng để build 'FACTS USER ĐÃ NÊU' block trong prompt, giúp Gemini
        phản ánh facts trước khi hỏi (không hỏi lại thông tin user đã cung cấp).

        Hiện tại: rule-based đơn giản với regex/keyword. Có thể nâng cấp sau.

        Returns:
            List các fact ngắn gọn (string). Ví dụ: ["thiếu 2 người", "deadline ngày mai"]
        """
        facts: List[str] = []
        msg = message.strip()
        if not msg:
            return facts

        # 1. Số lượng người / deadline (hỗ trợ cả số chữ: một, hai, ba, ...)
        NUMBER_WORDS = r"(một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|\d+)"
        patterns = [
            (rf"thiếu\s+{NUMBER_WORDS}\s*người", "thiếu nhiều người (nhóm thiếu nhân sự)"),
            (r"chỉ tiêu\s+(vẫn\s+)?(giữ nguyên|không đổi|vẫn vậy|không thay đổi)", "chỉ tiêu không giảm (áp lực cũ)"),
            (r"deadline\s+(ngày mai|sáng mai|chiều mai|tối mai|hôm nay|tuần này)", "deadline {0}"),
            (rf"(đã kiểm tra|đã xem)\s+{NUMBER_WORDS}\s*lần", "đã kiểm tra nhiều lần"),
        ]
        for pat, template in patterns:
            m = re.search(pat, msg, re.IGNORECASE)
            if m:
                # Lấy group đầu tiên có giá trị
                groups = [g for g in m.groups() if g]
                if groups:
                    facts.append(template.format(*groups))
                else:
                    # Pattern match nhưng không có capture group → dùng text gốc
                    facts.append(template.format(""))

        # 2. Đã thử hành động gì
        action_patterns = [
            r"đã\s+trao đổi\s+với\s+quản lý",
            r"đã\s+nói\s+với\s+quản lý",
            r"đã\s+thử\s+([\w\s]{2,30})",
        ]
        for pat in action_patterns:
            m = re.search(pat, msg, re.IGNORECASE)
            if m:
                matched = m.group(0).strip()
                if matched and matched not in facts:
                    facts.append(matched)

        # 3. Cảm xúc từ ngữ rõ ràng (chỉ khi có từ khóa rõ ràng)
        emotion_keywords = {
            "sợ mắc lỗi": "lo sợ mắc lỗi",
            "sợ sai": "lo sợ sai sót",
            "không muốn nghỉ việc": "không muốn nghỉ việc",
            "muốn giảm": "muốn giảm",
        }
        for kw, fact in emotion_keywords.items():
            if kw in msg.lower() and fact not in facts:
                facts.append(fact)

        return facts

    def _get_used_topics(self, session_id: Optional[str]) -> set:
        """Đọc used_topics từ Firestore session document."""
        if not session_id:
            return set()
        try:
            session = self._session_repo.get_session(session_id)
            if session and getattr(session, "used_topics", None):
                return set(session.used_topics)
        except Exception:
            # Không block chat flow nếu Firestore lỗi
            pass
        return set()

    def _mark_used(
        self, session_id: Optional[str], topic: str, used_topics: set
    ) -> None:
        """Đánh dấu topic đã dùng + persist lên Firestore."""
        if not session_id or not topic:
            return
        try:
            self._session_repo.add_used_topic(session_id, topic)
            used_topics.add(topic)
        except Exception:
            # Best-effort: vẫn giữ in-memory để không hỏi lặp trong cùng request
            used_topics.add(topic)

    def _get_fallback_question(
        self, session_id: Optional[str], used_topics: set
    ) -> ProbingQuestion:
        # Sửa GAP-9: duyệt TẤT CẢ topic, không chỉ 5 topic đầu
        # Thứ tự ưu tiên dựa trên khả năng phổ biến trong burnout screening
        priority_order = [
            "workload", "recovery", "deadline", "task_switching",
            "support", "autonomy", "disengagement",
        ]
        for topic in priority_order:
            if topic not in used_topics and topic in STA_QUESTION_CATALOG:
                self._mark_used(session_id, topic, used_topics)
                return STA_QUESTION_CATALOG[topic]
        # Nếu đã dùng hết 7 topic, trả về probing trung tính
        # PR 1 (P0-03): Reflection KHÔNG suy diễn khi không có bằng chứng.
        # Micro-action thay "hít thở sâu" bằng câu mời chia sẻ thêm,
        # vì ở đây user đã dùng hết topic, ta không ép hành động cụ thể.
        return ProbingQuestion(
            topic="general",
            target_dimension="Tổng quát",
            data_objective="Mời người dùng chia sẻ thêm (không suy diễn)",
            question="Có điều gì khác bạn muốn chia sẻ thêm không?",
            reflection_template="",  # Trống: không phản ánh gì khi chưa có dữ liệu
            micro_action="",  # Trống: không ép hành động khi chưa rõ nguyên nhân
            keywords=[],
        )

    def select_micro_action(
        self,
        question: ProbingQuestion,
        user_message: str = "",
        context_facts: Optional[List[str]] = None,
    ) -> str:
        """PR 2: Chọn micro-action phù hợp với context user.

        Quy tắc ưu tiên (không tốn Gemini call):
        1. Nếu user đã thử hành động → dùng action điều kiện 'user_tried_already'
        2. Nếu có fact 'team_shortage' → dùng action điều kiện
        3. Nếu không match → dùng micro_action mặc định
        4. Nếu cả 3 rỗng → trả '' (không ép hành động)

        Args:
            question: ProbingQuestion đã được chọn.
            user_message: Tin nhắn gốc của user (để detect 'đã thử').
            context_facts: List facts đã extract (từ session.context_facts).

        Returns:
            Micro-action string phù hợp.
        """
        # 1. Detect 'user đã thử hành động'
        tried_patterns = [
            r"đã\s+(trao đổi|nói|thử|gặp|xin phép|yêu cầu|đề xuất)",
            r"đã\s+làm\s+",
            r"từng\s+(thử|cố)",
        ]
        user_tried = any(
            re.search(pat, user_message, re.IGNORECASE) for pat in tried_patterns
        )

        # 2. Check facts từ session
        facts_text = " ".join(context_facts or []).lower()
        has_team_shortage = bool(
            re.search(r"thiếu\s+(\d+|hai|ba|bốn|năm|\d+)\s*người", facts_text)
            or "thiếu nhân sự" in facts_text
            or "thiếu nhiều người" in facts_text
        )

        # 3. Chọn action theo priority
        cond = question.micro_action_conditional or {}
        if user_tried and cond.get("user_tried_already"):
            return cond["user_tried_already"]
        if has_team_shortage and cond.get("team_shortage"):
            return cond["team_shortage"]

        return question.micro_action  # default

    def select_question_variant(
        self,
        question: ProbingQuestion,
        user_message: str = "",
        history_text: str = "",
    ) -> str:
        """PR 2: Chọn biến thể câu hỏi để tránh lặp form.

        Logic đơn giản: nếu history_text chứa form câu hỏi chính → dùng variant.
        Nếu có nhiều variant → chọn ngẫu nhiên có trọng số (ưu tiên variant).
        """
        variants = question.question_variants or []
        if not variants:
            return question.question

        # Nếu câu hỏi chính đã xuất hiện trong history → ưu tiên variant
        main_used = question.question[:40] in history_text  # check 40 ký tự đầu
        if main_used:
            import random
            return random.choice(variants)

        return question.question

    def detect_user_wants_to_stop(self, user_message: str) -> bool:
        """PR 2 (Test 9): Detect user muốn dừng/không muốn tiếp tục.

        Trả True nếu user nói rõ không muốn chia sẻ thêm.
        False Positive nguy hiểm: nếu nhầm → bỏ lỡ cơ hội hỗ trợ user.
        Nên chỉ match các pattern rõ ràng.
        """
        msg_lower = user_message.lower().strip()
        if not msg_lower:
            return False

        stop_phrases = [
            "không muốn nói thêm",
            "khong muon noi them",
            "chưa muốn nói",
            "chua muon noi",
            "thôi nhé",
            "thoi nhe",
            "thôi",
            "dừng lại",
            "dung lai",
            "ngừng",
            "ngung",
            "không tiếp tục",
            "khong tiep tuc",
            "tạm dừng",
            "tam dung",
            "hết rồi",
            "het roi",
            "không cần nữa",
            "khong can nua",
            "đủ rồi",
            "du roi",
            "cảm ơn nhé",
            "cam on nhe",
            "cảm ơn",
            "cam on",
        ]
        for phrase in stop_phrases:
            if phrase in msg_lower:
                return True
        return False

    def clear_assessment_questions(self, assessment_id: str) -> None:
        """Legacy: giữ API cũ, không còn dùng (state đã ở Firestore)."""
        return None


# Singleton
_probing_service: Optional[ProbingQuestionsService] = None


def get_probing_questions_service() -> ProbingQuestionsService:
    global _probing_service
    if _probing_service is None:
        _probing_service = ProbingQuestionsService()
    return _probing_service
