"""
Unit tests cho STA Chat v2.2 (Sửa dứt điểm 4 lỗi).
1. CRISIS-01: Bộ lọc an toàn khủng hoảng nhận diện tín hiệu tự hại ngầm định.
2. STATE-01: State machine kích hoạt chuẩn xác Turn 2.5 (clarifying_cause) khi Turn 1 kiệt sức.
3. FALLBACK-01: Phản hồi fallback không bị lặp từ khi thiếu survey_context.
4. INFRA-01: GeminiRotator xoay vòng key và model thông minh khi chạm quota.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.modules.chat.services.chat_response_generator import (
    evaluate_crisis_safety,
    get_chat_response_generator,
)
from app.modules.chat.routes.chat_history import (
    decide_stage,
    is_fatigued_short_message,
)
from app.core.gemini_rotator import GeminiRotator


# ==========================================
# 1. CRISIS-01 TESTS
# ==========================================

def test_crisis_passive_suicidal_ideation():
    """Kiểm tra nhận diện ý niệm tự hại ngầm định (TC-OUT-08)."""
    danger_phrases = [
        "Nhiều lúc tôi chỉ ước ngày mai mình không bao giờ phải tỉnh dậy nữa... mệt quá rồi, buông xuôi thôi.",
        "Tôi chỉ muốn ngủ một giấc không bao giờ dậy nữa.",
        "Tôi thấy bế tắc hoàn toàn, sống làm gì nữa.",
        "Buông xuôi thôi, mệt mỏi quá rồi.",
        "Chết đi cho rồi, không muốn tiếp tục nữa.",
        "Chết cho xong, hết chịu nổi rồi.",
        "Muốn biến mất khỏi thế giới này.",
    ]
    for phrase in danger_phrases:
        is_crisis, reply = evaluate_crisis_safety(phrase)
        assert is_crisis is True, f"Failed to detect crisis in: {phrase}"
        assert reply is not None
        assert "115" in reply


def test_crisis_colloquial_and_negation():
    """Kiểm tra không bắt nhầm thành ngữ thông tục hoặc câu phủ định."""
    safe_phrases = [
        "Hôm nay công việc mệt chết đi được.",
        "Chán chết với ông sếp độc tài.",
        "Buông xuôi tay lái khi đi xe.",
        "Tôi không muốn chết đâu, chỉ là mệt mỏi cần nghỉ ngơi.",
        "Tôi không có ý định tự tử, bạn đừng lo.",
    ]
    for phrase in safe_phrases:
        is_crisis, _ = evaluate_crisis_safety(phrase)
        assert is_crisis is False, f"False positive detected in: {phrase}"


# ==========================================
# 2. STATE-01 TESTS (Fatigued Path)
# ==========================================

def test_is_fatigued_short_message():
    assert is_fatigued_short_message("mệt") is True
    assert is_fatigued_short_message("met") is True
    assert is_fatigued_short_message("không biết") is True
    assert is_fatigued_short_message("ổn") is True
    # Dài hơn 15 ký tự -> False
    assert is_fatigued_short_message("chẳng biết nói gì nữa, công việc quá tải thôi") is False


def test_fatigued_state_machine_4_turns():
    """Chuẩn xác lộ trình 4 lượt khi Lượt 1 bị kiệt sức."""
    # Turn 1
    s1, comp1, reply1, ext1 = decide_stage(
        current_turn_count=1,
        is_crisis_active=False,
        is_fatigued_short=True,
        was_extended=False,
        new_msg_is_crisis=False,
    )
    assert s1 == "greeting_and_probe"
    assert comp1 is False
    assert reply1 is True

    # Turn 2 (Được kích hoạt bởi cờ was_fatigued_turn1=True)
    s2, comp2, reply2, ext2 = decide_stage(
        current_turn_count=2,
        is_crisis_active=False,
        is_fatigued_short=True, # was_fatigued_turn1
        was_extended=False,
        new_msg_is_crisis=False,
    )
    assert s2 == "clarifying_cause"
    assert comp2 is False
    assert ext2 is True

    # Turn 3
    s3, comp3, reply3, ext3 = decide_stage(
        current_turn_count=3,
        is_crisis_active=False,
        is_fatigued_short=False,
        was_extended=True,
        new_msg_is_crisis=False,
    )
    assert s3 == "reflect_and_support"
    assert comp3 is False

    # Turn 4
    s4, comp4, reply4, ext4 = decide_stage(
        current_turn_count=4,
        is_crisis_active=False,
        is_fatigued_short=False,
        was_extended=True,
        new_msg_is_crisis=False,
    )
    assert s4 == "wrapping_up"
    assert comp4 is True
    assert reply4 is False


# ==========================================
# 3. FALLBACK-01 TESTS
# ==========================================

def test_fallback_greeting_phrasing():
    gen = get_chat_response_generator()
    # Khi survey_context rỗng -> không bị "áp lực từ áp lực công việc"
    res_empty = gen._stage_aware_fallback("greeting_and_probe", survey_context=None)
    assert "áp lực từ áp lực" not in res_empty
    assert "căng thẳng trong công việc" in res_empty
    assert "?" in res_empty

    # Khi có dữ liệu overload_reasons
    res_data = gen._stage_aware_fallback("greeting_and_probe", survey_context={"overload_reasons": ["deadline", "thiếu người"]})
    assert "áp lực từ deadline, thiếu người" in res_data


# ==========================================
# 4. INFRA-01 TESTS (GeminiRotator)
# ==========================================

def test_gemini_rotator_model_pool_and_keys():
    from app.core.settings import get_settings
    settings = get_settings().google_ai
    rotator = GeminiRotator()

    keys = rotator._get_keys()
    assert len(keys) >= 1
    models = rotator._get_models()
    assert "gemini-3.6-flash" in models
    assert "gemini-3.5-flash-lite" in models


def test_gemini_rotator_failover_logic():
    rotator = GeminiRotator()
    calls = []

    def mock_call(client, model):
        calls.append(model)
        if model == "gemini-3.6-flash":
            raise RuntimeError("429 RESOURCE_EXHAUSTED Quota exceeded limit: 20 per day")
        if model == "gemini-3.5-flash-lite":
            raise RuntimeError("503 UNAVAILABLE Model High Demand")
        return f"OK from {model}"

    res, model_used, _ = rotator.execute_with_failover(mock_call)
    assert res == "OK from gemini-3.1-flash-lite"
    assert model_used == "gemini-3.1-flash-lite"
    assert "gemini-3.6-flash" in calls
    assert "gemini-3.5-flash-lite" in calls


# ==========================================
# 5. USER EXTENSION TESTS (STA v2.3)
# ==========================================

@pytest.mark.parametrize("fatigued,base_end", [(False, 3), (True, 4)])
def test_user_extension_is_exactly_three_turns(fatigued, base_end):
    stages = []
    for offset in range(1, 4):
        stage, completed, can_reply, _ = decide_stage(
            current_turn_count=base_end + offset, is_crisis_active=False,
            is_fatigued_short=fatigued, was_extended=fatigued,
            new_msg_is_crisis=False, user_extended=True,
        )
        stages.append(stage)
        assert completed is (offset == 3)
        assert can_reply is (offset < 3)
    assert stages == ["clarifying_cause", "reflect_and_support", "wrapping_up"]


# ==========================================
# 6. PR 1 TESTS - P0-01: Negation handling
# ==========================================

def test_negation_excludes_support_topic():
    """Test 5 (spec): 'Tôi không thiếu hỗ trợ từ đồng nghiệp...' → KHÔNG chọn support."""
    from app.modules.chat.services.probing_questions import get_probing_questions_service
    svc = get_probing_questions_service()

    # Phủ định rõ ràng
    topic = svc._detect_topic_from_text(
        "Tôi không thiếu hỗ trợ từ đồng nghiệp. Vấn đề là quản lý thay đổi yêu cầu liên tục.",
        used_topics=set(),
    )
    assert topic != "support", f"'support' bị loại do phủ định, nhưng kết quả = {topic}"


def test_negation_excludes_recovery_when_user_not_sleepy():
    """Phủ định 'không mệt' loại recovery khỏi match."""
    from app.modules.chat.services.probing_questions import get_probing_questions_service
    svc = get_probing_questions_service()

    topic = svc._detect_topic_from_text(
        "Tôi không mệt, chỉ là deadline dí sát.",
        used_topics=set(),
    )
    # 'mệt' bị phủ định → recovery bị loại. Còn lại: 'deadline'
    # Có thể trả 'deadline' (đúng) hoặc None (chấp nhận được)
    if topic is not None:
        assert topic != "recovery", f"recovery bị loại do phủ định, nhưng kết quả = {topic}"


def test_no_negation_still_matches():
    """Sanity check: không có phủ định → vẫn match bình thường."""
    from app.modules.chat.services.probing_questions import get_probing_questions_service
    svc = get_probing_questions_service()

    topic = svc._detect_topic_from_text(
        "Tôi đang quá tải với khối lượng công việc.",
        used_topics=set(),
    )
    assert topic == "workload", f"Không có phủ định, kỳ vọng 'workload', kết quả = {topic}"


def test_negation_reset_after_comma():
    """Phủ định bị reset sau dấu phẩy: 'tôi không X, mà là Y' → Y match bình thường."""
    from app.modules.chat.services.probing_questions import (
        get_probing_questions_service,
    )
    # Mock instance để test static method
    svc = get_probing_questions_service()

    # "Tôi không thiếu người, nhưng tôi thiếu hỗ trợ" → 'thiếu hỗ trợ' KHÔNG bị phủ định
    # vì phủ định 'không' ở câu trước bị ngắt bởi dấu phẩy
    msg = "Tôi không thiếu người, nhưng tôi thiếu hỗ trợ kỹ thuật."
    # 'hỗ trợ' có phủ định 'không' trước nó không? Check trực tiếp
    # Phần trước 'hỗ trợ' = "Tôi không thiếu người, nhưng tôi thiếu "
    # Sau dấu phẩy reset, 4 token gần nhất: ["nhưng", "tôi", "thiếu", ""] → không có 'không'
    # → KHÔNG phủ định
    assert svc._is_keyword_negated(msg, "hỗ trợ") is False, \
        "Sau dấu phẩy, phủ định phải bị reset"


# ==========================================
# 7. PR 1 TESTS - P0-02: Fact extraction
# ==========================================

def test_extract_facts_resource_constraint():
    """Test 3 (spec): 'Nhóm thiếu hai người...' → extract fact về thiếu người + chỉ tiêu."""
    from app.modules.chat.services.probing_questions import get_probing_questions_service
    svc = get_probing_questions_service()

    facts = svc.extract_facts("Nhóm thiếu hai người nhưng chỉ tiêu vẫn giữ nguyên.")
    assert len(facts) >= 2, f"Phải extract ít nhất 2 facts (thiếu người + chỉ tiêu), kết quả = {facts}"
    # Check có fact về thiếu người
    assert any("thiếu" in f.lower() and "người" in f.lower() for f in facts), \
        f"Kỳ vọng fact về thiếu người, kết quả = {facts}"
    # Check có fact về chỉ tiêu
    assert any("chỉ tiêu" in f for f in facts), \
        f"Kỳ vọng fact về chỉ tiêu, kết quả = {facts}"


def test_extract_facts_user_tried_action():
    """Test 8 (spec): 'Tôi đã trao đổi với quản lý rồi...' → extract fact hành động đã thử."""
    from app.modules.chat.services.probing_questions import get_probing_questions_service
    svc = get_probing_questions_service()

    facts = svc.extract_facts(
        "Tôi đã trao đổi với quản lý rồi nhưng khối lượng công việc vẫn không đổi."
    )
    assert any("trao đổi" in f or "quản lý" in f for f in facts), \
        f"Kỳ vọng fact hành động đã thử, kết quả = {facts}"


def test_extract_facts_empty_for_uncertain():
    """Test 7 (spec): 'Tôi thấy không ổn lắm...' → không extract fact (uncertain)."""
    from app.modules.chat.services.probing_questions import get_probing_questions_service
    svc = get_probing_questions_service()

    facts = svc.extract_facts("Tôi thấy không ổn lắm trong mấy ngày nay.")
    # Không có fact cụ thể nào (không có số, deadline, hành động)
    # Có thể trả list rỗng hoặc chỉ chứa các keyword cảm xúc
    # Quan trọng: KHÔNG có fact "thiếu người", "deadline" v.v.
    for f in facts:
        assert "người" not in f or "thiếu" in f, \
            f"Fact '{f}' không nên xuất hiện khi user nói chung chung"


# ==========================================
# 8. PR 1 TESTS - P0-03: Fallback reflection không suy diễn
# ==========================================

def test_general_fallback_no_speculation():
    """Khi đã dùng hết 7 topic, general fallback phải KHÔNG có reflection_template
    và micro_action mặc định (P0-03: không suy diễn)."""
    from app.modules.chat.services.probing_questions import (
        ProbingQuestion,
        get_probing_questions_service,
    )
    svc = get_probing_questions_service()

    # Mock: tất cả 7 topic đều used
    used = {"workload", "recovery", "deadline", "task_switching",
            "support", "autonomy", "disengagement"}
    result = svc._get_fallback_question(session_id=None, used_topics=used)

    assert result.topic == "general"
    # PR 1: reflection_template và micro_action phải RỖNG (không suy diễn)
    assert result.reflection_template == "", \
        f"Không nên suy diễn reflection khi chưa có dữ liệu, kết quả = '{result.reflection_template}'"
    assert result.micro_action == "", \
        f"Không nên ép micro-action khi chưa rõ nguyên nhân, kết quả = '{result.micro_action}'"


# ==========================================
# 9. PR 2 TESTS - Variants + Conditional Micro-actions
# ==========================================

def test_pr2_question_variants_exist():
    """Mỗi topic phải có question_variants để tránh lặp form."""
    from app.modules.chat.services.probing_questions import STA_QUESTION_CATALOG
    for topic, q in STA_QUESTION_CATALOG.items():
        assert len(q.question_variants) >= 1, \
            f"Topic '{topic}' thiếu question_variants"


def test_pr2_conditional_micro_action_when_user_tried():
    """Test 8 (spec): User đã thử hành động → micro-action khác (không đề xuất lại)."""
    from app.modules.chat.services.probing_questions import (
        STA_QUESTION_CATALOG,
        get_probing_questions_service,
    )
    svc = get_probing_questions_service()
    workload_q = STA_QUESTION_CATALOG["workload"]

    # Default action
    default_action = svc.select_micro_action(workload_q, user_message="")
    assert default_action == workload_q.micro_action

    # User đã thử → action khác
    tried_action = svc.select_micro_action(
        workload_q, user_message="Tôi đã trao đổi với quản lý rồi mà không đổi"
    )
    assert tried_action != default_action
    assert "quản lý" in tried_action.lower() or "thống nhất" in tried_action.lower(), \
        f"Action khi user đã thử nên đề cập đến giải pháp nhóm, kết quả = '{tried_action}'"


def test_pr2_conditional_micro_action_team_shortage():
    """User có fact 'thiếu người' → dùng team_shortage action nếu có."""
    from app.modules.chat.services.probing_questions import (
        STA_QUESTION_CATALOG,
        get_probing_questions_service,
    )
    svc = get_probing_questions_service()
    workload_q = STA_QUESTION_CATALOG["workload"]

    # Facts có 'thiếu người'
    action = svc.select_micro_action(
        workload_q,
        user_message="",
        context_facts=["thiếu nhiều người (nhóm thiếu nhân sự)"],
    )
    # workload có conditional team_shortage → phải dùng
    assert "đề xuất hoãn" in action.lower() or "thiếu người" in action.lower() or "nhóm" in action.lower(), \
        f"Action cho team shortage phải liên quan đến hoãn việc, kết quả = '{action}'"


def test_pr2_select_question_variant_uses_variant_when_main_repeated():
    """Nếu câu hỏi chính đã xuất hiện trong history → dùng variant."""
    from app.modules.chat.services.probing_questions import (
        STA_QUESTION_CATALOG,
        get_probing_questions_service,
    )
    svc = get_probing_questions_service()
    workload_q = STA_QUESTION_CATALOG["workload"]
    main_start = workload_q.question[:40]

    # History chứa câu hỏi chính
    history_with_main = f"AI trước đó: {main_start} ... và các chi tiết khác"
    result = svc.select_question_variant(workload_q, history_text=history_with_main)

    # Kết quả phải là variant (không phải câu hỏi chính)
    assert result != workload_q.question
    assert result in workload_q.question_variants


def test_pr2_select_question_variant_default_when_no_history():
    """Khi history không có câu hỏi chính → dùng câu hỏi chính."""
    from app.modules.chat.services.probing_questions import (
        STA_QUESTION_CATALOG,
        get_probing_questions_service,
    )
    svc = get_probing_questions_service()
    workload_q = STA_QUESTION_CATALOG["workload"]

    result = svc.select_question_variant(workload_q, history_text="")
    assert result == workload_q.question


# ==========================================
# 10. PR 2 TESTS - User wants to stop detection (Test 9)
# ==========================================

def test_pr2_detect_user_wants_to_stop():
    """Test 9 (spec): 'Tôi chưa muốn nói thêm lúc này' → tôn trọng."""
    from app.modules.chat.services.probing_questions import get_probing_questions_service
    svc = get_probing_questions_service()

    stop_phrases = [
        "Tôi chưa muốn nói thêm lúc này",
        "thôi nhé, tôi cần nghỉ",
        "cảm ơn nhé",
        "tạm dừng được rồi",
        "đủ rồi",
    ]
    for phrase in stop_phrases:
        assert svc.detect_user_wants_to_stop(phrase) is True, \
            f"Phải detect user muốn dừng: {phrase}"


def test_pr2_no_false_positive_on_normal_messages():
    """Normal message KHÔNG bị nhầm là muốn dừng."""
    from app.modules.chat.services.probing_questions import get_probing_questions_service
    svc = get_probing_questions_service()

    normal_phrases = [
        "Tôi đang rất áp lực với công việc",
        "Hôm nay tôi mệt quá",
        "Tôi cần nói chuyện thêm",
        "Công việc của tôi đang ổn",
    ]
    for phrase in normal_phrases:
        assert svc.detect_user_wants_to_stop(phrase) is False, \
            f"False positive - KHÔNG nên detect user muốn dừng: {phrase}"


# ==========================================
# 11. PR 2 TESTS - Generator returns cached topic (cache probe)
# ==========================================

def test_pr2_generator_returns_cached_topic():
    """Khi gọi generate_response, ChatResponse.follow_up_topic phải chứa topic name
    để route dùng cho Context Tagging mà không cần gọi lại probing_service."""
    from app.modules.chat.services.chat_response_generator import (
        get_chat_response_generator,
    )
    from app.modules.chat.services.probing_questions import get_probing_questions_service

    gen = get_chat_response_generator()
    probe_svc = get_probing_questions_service()

    # Mock _generate_with_gemini để tránh gọi API thật
    gen._generate_with_gemini = lambda prompt: ("Phản ánh test.", "STOP")

    result = gen.generate_response(
        user_message="Tôi đang quá tải với khối lượng công việc",
        stage="greeting_and_probe",
        survey_context=None,
        session_id=None,  # Không persist
        assessment_id="test",
        message_count=1,
    )
    # follow_up_topic phải là topic name (workload, recovery, ...)
    expected_topic = probe_svc._detect_topic_from_text(
        "Tôi đang quá tải với khối lượng công việc", used_topics=set()
    )
    assert result.follow_up_topic == expected_topic, \
        f"follow_up_topic phải cache topic, kỳ vọng {expected_topic}, " \
        f"kết quả = {result.follow_up_topic}"


def test_pr2_generator_user_stopped_short_circuits():
    """Khi user nói muốn dừng, generator trả về fallback mà KHÔNG gọi Gemini."""
    from app.modules.chat.services.chat_response_generator import (
        get_chat_response_generator,
    )
    gen = get_chat_response_generator()

    # Mock để check Gemini KHÔNG được gọi
    called = {"value": False}
    def mock_gemini(prompt):
        called["value"] = True
        return ("Should not be called", "STOP")
    gen._generate_with_gemini = mock_gemini

    result = gen.generate_response(
        user_message="Tôi chưa muốn nói thêm",
        stage="greeting_and_probe",
        session_id=None,
        assessment_id="test",
    )
    assert called["value"] is False, "Gemini KHÔNG nên được gọi khi user muốn dừng"
    assert result.finish_reason == "USER_STOPPED"
    assert "tôn trọng" in result.content.lower() or "cảm ơn" in result.content.lower()
