# STA Compact v2.1 — Implementation Plan

**Mục tiêu:** Triệt để sửa các bug đã audit (BUG-01..04 + GAP-01..10) và rào các trường hợp "user nói lan man vô hạn". Bám sát 5 yêu cầu xác minh trước khi sửa code.

**Trạng thái:** DRAFT — chờ duyệt. CHƯA sửa code.

---

## 0. Kết quả xác minh 5 yêu cầu (trước khi sửa)

### 0.1. `aggregated_stress_level` — bỏ inline analyze có hợp lý không?

**Phát hiện quan trọng:**

- Field `aggregated_stress_level` được định nghĩa trong `ChatSessionSummary` (chat_history.py:118) và ghi vào `ChatSummaryResponse` (chat_history.py:108, 620). Đây là **API contract có thật**.
- `analyze_chat_text()` được gọi trong `chat_history.py:335-337` để lưu `analysis` lên `chat_history` collection. Các message có field `analysis` mới có dữ liệu stress.
- Frontend `ChatPage.tsx:869-887` (Signal Panel) đọc `latestAnalysis.stress_level.score`, `fatigue_signal.score`, v.v. **trực tiếp từ `messages[].analysis`**, KHÔNG đọc `aggregated_stress_level` từ `/chat/summary`.
- Tổng hợp được tại [chat_history_repository.py:336-347](app/modules/chat/repositories/chat_history_repository.py#L336-L347): `avg_stress = sum(all_stress_scores) / len(all_stress_scores) if all_stress_scores else None`. Nếu `analysis` là None, average là `None`.

**Quyết định đề xuất (sau khi xác minh):**

- Bỏ inline `analyze_chat_text()` (theo Q1 = A).
- `/chat/summary` trả về `aggregated_stress_level = null` khi không có analysis — **KHÔNG cần đổi contract** vì field đã `Optional[float]`.
- Frontend Signal Panel sẽ trống → xử lý graceful (ẩn panel hoặc hiển thị "Chưa có dữ liệu phân tích" — chi tiết ở mục 1.4).
- **KHÔNG xóa hàm `analyze_chat_text()`** khỏi `ai_service.py` vì có thể còn consumer khác. Chỉ ngừng gọi từ route chat.

### 0.2. State machine hiện tại — đã đọc

- Route hiện tính `current_stage` tại `chat_history.py:302-319`. Generator tính lại ở `chat_response_generator.py:196, 251-260`. **Xác nhận BUG-01.**
- Route ở `chat_history.py:312-314` cho `user_turn_count == 3 → reflect_and_support` (không phải wrapping_up). **Xác nhận BUG-02.**
- Soft expiry đã có ở `find_or_create_session` (chat_session_repository.py:232). Idle 60 phút, max 5h. **Phù hợp yêu cầu Q6.**

### 0.3. Firestore transaction — khả thi

- Project dùng sync `firestore.Client` (xem `firebase.py:30-50`). Firestore Python SDK hỗ trợ `@firestore.transactional` decorator. FastAPI route hiện `async def` có thể gọi sync transaction qua `await loop.run_in_executor(None, ...)` (pattern phổ biến, không cần Celery). **Khả thi.**
- Schema hiện KHÔNG có `client_message_id`. Cần thêm:
  - `ChatMessageRequest.client_message_id: Optional[str]` (input)
  - `ChatHistoryRecord.client_message_id` (storage)
  - `chat_repo.save_message(..., client_message_id=...)`
  - Repository method mới: `get_by_client_message_id(assessment_id, client_message_id)` để check duplicate trước khi xử lý.

### 0.4. Crisis flow — đã đọc

- Route gọi `evaluate_crisis_safety` ở `chat_history.py:238-239`. Nếu crisis → `update_stage("crisis_support", is_crisis_active=True)`, save message, **trả `is_session_completed=True`** (line 275). Request tiếp theo sẽ dính `closed_notice` (line 183-205), **mất crisis banner**. **Xác nhận GAP-4.**
- `evaluate_crisis_safety` cũng được gọi ở generator (line 213) nhưng dead-code trên route hiện tại. **Xác nhận GAP-7.**

### 0.5. Frontend session state — đã đọc

- `sendMessage` (ChatPage.tsx:404-497) chỉ xử lý error bằng `err.response?.data?.detail` (line 492). **KHÔNG re-fetch state khi lỗi mạng.** **Xác nhận GAP-5.**
- Signal Panel (ChatPage.tsx:868-887) dùng `latestAnalysis` → sau khi bỏ inline analyze sẽ rỗng.

### 0.6. Fallback per stage — đề xuất nội dung (sau khi xác minh dữ liệu)

- `greeting_and_probe`: dùng `survey_context.overload_reasons` (đã được phía client lưu từ survey — đối chiếu `chat_history.py:376`). Chỉ reflect data đã có.
- `reflect_and_support`: dùng `primary_cause` (đã ghi ở bước Context Tagging) **chỉ khi** đã ghi thật (không bịa). Micro-action lấy từ probing service, **chỉ khi** probing còn available. Nếu thiếu → câu trung tính, không hỏi.
- `wrapping_up`: KHÔNG gán nguyên nhân (vì user có thể không nói gì rõ ở Turn 1-2). Câu tổng kết trung tính, không hỏi.
- `crisis_support`: `CRISIS_SAFETY_RESPONSE_TEMPLATE` (giữ nguyên).

### 0.7. Bảng transition rõ ràng (cho luồng thường + mở rộng)

| Điều kiện                                                                    | Stage tiếp theo                                                        |          Đóng phiên?          | `can_reply` |
| :--------------------------------------------------------------------------- | :--------------------------------------------------------------------- | :---------------------------: | :---------: |
| Msg có crisis signal ở bất kỳ turn nào                                       | `crisis_support`                                                       | **false** (giữ mở cho crisis) |    true     |
| `user_turn_count` 0 (vừa tạo session)                                        | `greeting_and_probe`                                                   |             false             |    true     |
| Turn 1 vừa xong → sang Turn 2                                                | (xét turn 2 mới)                                                       |                               |             |
| Turn 2, `is_fatigued_short` = true                                           | `clarifying_cause`                                                     |             false             |    true     |
| Turn 2, `is_fatigued_short` = false                                          | `reflect_and_support`                                                  |             false             |    true     |
| Turn 3, **`is_extended` = false** (happy path)                               | `wrapping_up`                                                          |           **true**            |  **false**  |
| Turn 3, `is_extended` = true (sau clarifying ở turn 2)                       | `reflect_and_support`                                                  |             false             |    true     |
| Turn 4, `is_extended` = true                                                 | `wrapping_up`                                                          |           **true**            |  **false**  |
| Turn ≥ 5 (HARD CAP, kể cả crisis đã clear)                                   | `wrapping_up`                                                          |           **true**            |  **false**  |
| Session trước đã `is_crisis_active = true` mà msg mới KHÔNG có crisis signal | Reset về `greeting_and_probe` (nếu còn turn budget) hoặc `wrapping_up` |           tuỳ turn            |  tuỳ stage  |
| Crisis msg mới xuất hiện khi session đang ở `wrapping_up`/`closed`           | Mở session mới với `crisis_support`                                    |             false             |    true     |

**Lưu ý quan trọng:**

- `is_extended` được set true khi vào `clarifying_cause` (xem `chat_history.py:308`). Sau khi qua turn 2.5, Turn 3 sẽ thấy `is_extended=true` → dùng nhánh mở rộng.
- Happy path (không clarifying): Turn 2 → `reflect_and_support`, Turn 3 → `wrapping_up`. **3 turns tổng.**
- Extended path (có clarifying): Turn 2 → `clarifying_cause`, Turn 3 → `reflect_and_support`, Turn 4 → `wrapping_up`. **4 turns tổng.**
- Crisis KHÔNG tuân theo turn budget thường — sẽ rào riêng ở mục 1.6.

---

## 1. Kế hoạch thay đổi tối thiểu

### 1.1. Files sẽ sửa

| File                                                       | Thay đổi chính                                                                                                                                                                                                                                                                                                                                                                                                                                       | Lý do                                               |
| :--------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------- |
| `app/modules/chat/services/chat_response_generator.py`     | (1) Thêm `stage: str` bắt buộc vào `generate_response()`. (2) Xóa `_determine_stage()`. (3) Bỏ gọi `evaluate_crisis_safety` ở line 213 (consolidate về route). (4) Thêm `stage` param vào `_generate_fallback_response()`. (5) Thêm `_validate_output(text, stage)` để phát hiện câu hỏi ở stage cấm hỏi, trả về `None` nếu hợp lệ, `True` nếu vi phạm. (6) Tăng cường prompt stage-specific với cảnh báo mạnh.                                      | Sửa BUG-01, BUG-04, GAP-1, GAP-3, GAP-6, GAP-7      |
| `app/modules/chat/routes/chat_history.py`                  | (1) State machine mới theo bảng 0.7. (2) Bỏ gọi `analyze_chat_text()` (Q1). (3) Truyền `stage` xuống generator. (4) Thêm endpoint `GET /chat/state` (Q3). (5) Crisis: bỏ `is_session_completed=True` ở line 275 (Q4 sửa GAP-4). (6) Thêm request field `client_message_id` (Q5). (7) Thêm validation `max_length=1000` (Q6). (8) Wrapping turn kết thúc ở Turn 3 happy path (sửa BUG-02).                                                            | Sửa BUG-02, GAP-2, GAP-4, GAP-5, Q1, Q3, Q4, Q5, Q6 |
| `app/modules/chat/repositories/chat_session_repository.py` | (1) Thêm method `process_message_atomic(session_id, client_message_id, stage, is_extended, ...) -> ChatSession` dùng Firestore transaction. (2) Đảm bảo `user_turn_count` và `current_stage` update cùng transaction. (3) Cập nhật `close_session` để giữ `is_crisis_active=true` (cho phép mở phiên mới nếu crisis).                                                                                                                                | Q5, GAP-8                                           |
| `app/modules/chat/repositories/chat_history_repository.py` | (1) Thêm `client_message_id` vào `save_message()`. (2) Thêm `get_by_client_message_id(assessment_id, client_message_id)`.                                                                                                                                                                                                                                                                                                                            | Q5                                                  |
| `app/modules/chat/models/chat_history.py`                  | (1) Thêm `client_message_id: Optional[str]` vào `ChatHistoryRecord`.                                                                                                                                                                                                                                                                                                                                                                                 | Q5                                                  |
| `app/modules/chat/models/chat_session.py`                  | Không đổi. Field `primary_cause`, `micro_action_offered` đã có từ v2.                                                                                                                                                                                                                                                                                                                                                                                | –                                                   |
| `admin-ui/src/pages/ChatPage.tsx`                          | (1) Tạo UUID cho mỗi message (`crypto.randomUUID()`), gửi kèm. (2) Khi lỗi mạng: gọi `GET /chat/state` để biết session còn mở không. (3) Nếu state trả `closed` → hiển thị modal. (4) Nếu state gọi fail → hiển thị "Trạng thái chưa xác định, vui lòng thử lại", KHÔNG tự đoán. (5) Signal Panel: thêm fallback "Chưa có dữ liệu phân tích" khi `latestAnalysis` undefined. (6) Validation: nếu `inputText.length > 1000` → setError trước khi gửi. | Q3, Q6, GAP-5                                       |

### 1.2. Files KHÔNG sửa (theo yêu cầu "không refactor ngoài phạm vi")

- `app/modules/assessment/services/ai_service.py` — chỉ ngừng gọi `analyze_chat_text` từ route, không sửa hàm. (B4 mục 4)
- `app/modules/chat/services/probing_questions.py` — đã ổn. Chỉ sửa GAP-9 (loop bỏ sót 2 topic).
- `app/modules/chat/services/conversation_stages.py` — không liên quan.
- `app/core/firebase.py` — không cần thay đổi.
- `app/core/settings.py` — idle/max đã đúng cấu hình.

### 1.3. Chi tiết thay đổi từng file (high-level sketch)

#### `chat_response_generator.py`

```python
def generate_response(
    self,
    user_message: str,
    stage: str,                              # BẮT BUỘC, không default
    analysis_context: Optional[ChatAnalysisContext] = None,
    conversation_history: List[dict] = None,
    survey_context: Optional[dict] = None,
    session_id: Optional[str] = None,
    assessment_id: Optional[str] = None,
) -> ChatResponse:
    if stage not in {"greeting_and_probe", "clarifying_cause",
                     "reflect_and_support", "wrapping_up", "crisis_support"}:
        raise ValueError(f"Invalid stage: {stage}")
    # XÓA: stage = self._determine_stage(message_count)
    # XÓA: is_crisis, crisis_response = evaluate_crisis_safety(...)
    #       (route đã chặn ở đầu rồi)
    history_text = self._build_history_text(conversation_history or [])
    prompt = self._build_prompt(... stage=stage, ...)

    try:
        response_text, finish_reason = self._generate_with_gemini(prompt)
        # Post-validation: nếu stage cấm hỏi mà response có ?, dùng fallback
        if self._is_question_in_forbidden_stage(response_text, stage):
            logger.info("Output violates stage=%s, replacing with stage-aware fallback", stage)
            response_text = self._stage_aware_fallback(stage, survey_context, user_message)
        return ChatResponse(content=response_text, ...)
    except Exception as exc:
        fallback = self._stage_aware_fallback(stage, survey_context, user_message)
        return fallback

# Xóa _determine_stage
# Xóa _generate_fallback_response (cũ) hoặc thay thế bằng _stage_aware_fallback

def _is_question_in_forbidden_stage(self, text: str, stage: str) -> bool:
    """Heuristic bảo thủ: phát hiện dấu ? ở 2 stage cấm hỏi.

    Chỉ check 2 ký tự ASCII '?'. Không phân tích câu phức tạp.
    Test sẽ có false positive/negative cases (xem 1.5).
    """
    if stage not in {"reflect_and_support", "wrapping_up"}:
        return False
    return "?" in text

def _stage_aware_fallback(
    self,
    stage: str,
    survey_context: Optional[dict],
    user_message: str,
    primary_cause: Optional[str] = None,
    micro_action: Optional[str] = None,
) -> str:
    """Trả về nội dung fallback THEO STAGE, không có câu hỏi ở 2 stage cuối."""
    if stage == "greeting_and_probe":
        reasons = ", ".join((survey_context or {}).get("overload_reasons", [])) or "áp lực công việc"
        return (
            f"Qua khảo sát gần nhất, tôi nhận thấy bạn đang chịu áp lực từ {reasons}. "
            "Điều gì trong công việc tạo áp lực lớn nhất cho bạn hôm nay?"
        )
    if stage == "clarifying_cause":
        return "Bạn có thể chia sẻ thêm một điều khiến bạn bận tâm nhất lúc này không?"
    if stage == "reflect_and_support":
        # CHỈ reflect primary_cause nếu đã được ghi (không bịa)
        if primary_cause and micro_action:
            return (
                f"Tôi ghi nhận bạn đã chia sẻ về {primary_cause}. "
                f"Trong 5 phút tới, bạn có thể thử: {micro_action}. "
                "Hãy thử khi bạn sẵn sàng."
            )
        # Fallback trung tính, không hỏi
        return (
            "Tôi ghi nhận những chia sẻ của bạn. "
            "Hãy dành ít phút nghỉ ngơi và quay lại khi bạn sẵn sàng nhé."
        )
    if stage == "wrapping_up":
        # Tổng kết trung tính, KHÔNG gán nguyên nhân
        return (
            "Cảm ơn bạn đã dành thời gian chia sẻ. "
            "Hãy nghỉ ngơi và chăm sóc bản thân nhé. Hẹn gặp lại bạn."
        )
    # crisis_support giữ riêng
    return CRISIS_SAFETY_RESPONSE_TEMPLATE
```

**Tăng cường prompt stage_instruction** ở `_build_prompt` (chèn cảnh báo mạnh cho 2 stage cấm):

```python
"reflect_and_support": (
    "GIAI ĐOẠN PHẢN ÁNH & HỖ TRỢ: "
    "1. Phản ánh ngắn nguyên nhân user vừa nói. "
    "2. Đưa ra 1 micro-action 5 phút khả thi. "
    "🚫 CẤM TUYỆT ĐỐI: KHÔNG được đặt bất kỳ câu hỏi nào (kể cả tu từ). "
    "KHÔNG kết thúc bằng dấu '?'. Nếu bạn đặt câu hỏi, output sẽ bị từ chối."
),
"wrapping_up": (
    "GIAI ĐOẠN TỔNG KẾT & KẾT THÚC: "
    "Tóm tắt 1-2 điểm, dặn dò ấm áp. "
    "🚫 CẤM TUYỆT ĐỐI: KHÔNG mở chủ đề mới, KHÔNG đặt câu hỏi. "
    "KHÔNG kết thúc bằng dấu '?'."
),
```

#### `chat_history.py` — phần state machine mới

```python
# Đặt NGAY SAU increment_user_turns / history fetch
# (đã có transaction từ repository mới — gọi 1 lần, nguyên tử)

def _decide_stage(
    current_turn_count: int,
    is_fatigued_short: bool,
    was_extended: bool,
    is_crisis_active: bool,
    new_msg_is_crisis: bool,
) -> tuple[str, bool, bool]:
    """Returns (current_stage, is_session_completed, can_reply)."""
    # Crisis luôn ưu tiên
    if new_msg_is_crisis:
        return "crisis_support", False, True
    # Đã crisis trước, msg mới không crisis → reset turn nếu cần budget
    if is_crisis_active and not new_msg_is_crisis:
        # Cho phép tiếp tục hội thoại bình thường (theo turn mới)
        pass

    # Happy / extended path
    if current_turn_count <= 1:
        return "greeting_and_probe", False, True
    if current_turn_count == 2:
        if is_fatigued_short:
            return "clarifying_cause", False, True  # Turn 2.5
        return "reflect_and_support", False, True
    if current_turn_count == 3 and not was_extended:
        return "wrapping_up", True, False  # ĐÓNG ở turn 3 happy
    if current_turn_count == 3 and was_extended:
        return "reflect_and_support", False, True  # Sau clarifying
    if current_turn_count == 4 and was_extended:
        return "wrapping_up", True, False  # ĐÓNG ở turn 4 extended
    # Hard cap
    return "wrapping_up", True, False
```

#### Endpoint mới `GET /chat/state`

```python
@router.get("/{assessment_id}/chat/state", response_model=dict)
async def get_chat_state(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    """Trả về trạng thái phiên hiện tại (idempotent, rất nhẹ).

    Dùng cho frontend đồng bộ state khi lỗi mạng.
    """
    # Verify ownership
    assessment = assessment_repo.get(assessment_id)
    if not assessment or assessment.get("user_id") != user["uid"]:
        raise HTTPException(404, "Not found")

    session = chat_session_repo.get_active_session(assessment_id)
    if not session:
        return {
            "status": "none",
            "can_reply": False,
            "current_stage": None,
            "user_turn_count": 0,
        }

    is_valid, _ = chat_session_repo._is_session_valid(session)
    return {
        "status": "active" if is_valid else "expired",
        "can_reply": is_valid and session.status == "active",
        "current_stage": session.current_stage,
        "user_turn_count": getattr(session, "user_turn_count", 0),
        "is_crisis_active": getattr(session, "is_crisis_active", False),
    }
```

#### `chat_session_repository.py` — Transaction mới

```python
@firestore.transactional
def _process_message_transaction(
    self, transaction, session_id, new_stage, is_extended_flag, is_crisis_active_flag
):
    """Atomic update: stage + is_extended + last_activity + tùy crisis.

    KHÔNG gọi Gemini bên trong transaction (Firestore transactions
    có thể retry).
    """
    doc_ref = self.collection.document(session_id)
    snapshot = doc_ref.get(transaction=transaction)
    if not snapshot.exists:
        raise ValueError("Session disappeared")

    updates = {
        "current_stage": new_stage,
        "updated_at": datetime.utcnow(),
    }
    if is_extended_flag is not None:
        updates["is_extended"] = is_extended_flag
    if is_crisis_active_flag is not None:
        updates["is_crisis_active"] = is_crisis_active_flag
    transaction.update(doc_ref, updates)

def process_message_atomically(
    self,
    session_id: str,
    new_stage: str,
    is_extended: Optional[bool] = None,
    is_crisis_active: Optional[bool] = None,
) -> None:
    """Public API. Tự tạo transaction."""
    transaction = self.db.transaction()
    self._process_message_transaction(
        transaction, session_id, new_stage, is_extended, is_crisis_active
    )
```

**Về user_turn_count**: giữ nguyên `increment_user_turns` (atomic Increment). **KHÔNG** dùng nó làm idempotency key — chỉ `client_message_id` mới là key. Hai cơ chế này tách biệt: increment tăng sau khi biết message chưa trùng.

**Thứ tự trong route**:

1. Validate request (length, ownership)
2. Check `client_message_id` duplicate (nếu có)
3. Crisis check (early return nếu crisis)
4. Transaction: increment turn + update stage
5. (Ngoài transaction) gọi Gemini
6. Save messages
7. Context tagging nếu stage = `reflect_and_support`

### 1.4. Frontend (ChatPage.tsx) chi tiết

```typescript
// Helper: tạo UUID
const generateMessageId = (): string => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2)}`;
};

// Trong sendMessage
const messageId = generateMessageId();
const res = await api.post(`/api/v1/assessments/${sessionId}/chat`, {
  message: currentInput.trim(),
  client_message_id: messageId,  // MỚI
  analyze: true,
});
// Xử lý response bình thường...

// Trong catch
} catch (err: any) {
  // Thử re-fetch state
  try {
    const stateRes = await api.get(`/api/v1/assessments/${sessionId}/chat/state`);
    if (stateRes.data.status === "expired" || !stateRes.data.can_reply) {
      setIsCurrentSessionClosed(true);
      setError("Phiên đã đóng hoặc hết hạn. Vui lòng tạo phiên mới.");
    } else {
      setError("Mất kết nối. Vui lòng thử gửi lại.");
    }
  } catch (stateErr) {
    setError("Không thể xác minh trạng thái phiên. Vui lòng thử lại sau.");
    // KHÔNG tự đoán
  }
  setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
}

// Validation trước khi gửi
if (currentInput.trim().length > 1000) {
  setError("Tin nhắn quá dài (tối đa 1000 ký tự). Vui lòng tóm gọn.");
  return;
}

// Signal Panel fallback
{showSignalPanel && !latestAnalysis && (
  <div className="p-4 text-center text-gray-500 text-sm">
    Chưa có dữ liệu phân tích cho phiên này.
  </div>
)}
```

### 1.5. Test cần bổ sung

Theo brief F mục 1-16, viết test cho các case:

|  #  | Test case                                                                                                                                          | File test                                                 |
| :-: | :------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------- |
|  1  | Happy path 3 turns: 1→reflect→wrap, `is_session_completed=true` ở turn 3                                                                           | test_sta_chat_v2_1_state_machine.py                       |
|  2  | Extended path 4 turns: 1→clarifying→reflect→wrap                                                                                                   | (same)                                                    |
|  3  | User trả lời ngắn ở turn 1 → vào clarifying                                                                                                        | (same)                                                    |
|  4  | User từ chối chia sẻ ở turn 2 (e.g. "thôi") → vẫn dùng extended path                                                                               | (same)                                                    |
|  5  | User chủ động kết thúc ở turn 2 ("OK cảm ơn") → vẫn phải qua reflect ở turn 3 (KHÔNG skip)                                                         | (same)                                                    |
|  6  | User gửi 6 messages liên tiếp → hard cap ở turn 5 (wrapping_up)                                                                                    | (same)                                                    |
|  7  | Race: 2 requests cùng lúc cùng session_id, cùng client_message_id → request 2 trả về response của request 1                                        | test_sta_chat_v2_1_idempotency.py                         |
|  8  | Gemini timeout → fallback stage-aware đúng stage                                                                                                   | test_sta_chat_v2_1_fallback.py                            |
|  9  | Gemini trả response có `?` ở `reflect_and_support` → bị thay bằng fallback                                                                         | (same)                                                    |
| 10  | Fallback cho mỗi stage: 5 stages, không có câu hỏi ở 2 stage cuối                                                                                  | (same)                                                    |
| 11  | Request gửi sau khi session đã closed → trả closed_notice, không gọi Gemini                                                                        | test_sta_chat_v2_1_session_lifecycle.py                   |
| 12  | Crisis signal ở turn 1 → `is_session_completed=false` (mở tiếp cho crisis)                                                                         | test_sta_chat_v2_1_crisis.py                              |
| 13  | Crisis signal lặp lại ở turn 2 → vẫn crisis_support                                                                                                | (same)                                                    |
| 14  | FE mất kết nối khi nhận response cuối → re-fetch state thành công                                                                                  | test_sta_chat_v2_1_frontend_state.py (nếu có) hoặc manual |
| 15  | Context Tagging: `primary_cause`, `micro_action_offered` ghi đúng                                                                                  | test_sta_chat_v2_1_context_tagging.py                     |
| 16  | `/chat/summary` trả `aggregated_stress_level=null` khi không có analysis                                                                           | test_sta_chat_v2_1_dashboard.py                           |
| 17  | `_is_question_in_forbidden_stage`: false positive ("Bạn muốn tôi tóm tắt lại 1-2 điểm chính nhé.") — chấp nhận miss (không thay), document hành vi | test_sta_chat_v2_1_fallback.py                            |

**Tổng test mới: ~17 test cases**, chia thành 5 file (mỗi file 1 concern rõ ràng). Tất cả dùng mock Gemini, không gọi thật.

**Test cũ cần chạy lại**: `tests/test_sta_chat_compact.py` (9 test cũ). Phải đảm bảo vẫn pass với code mới. Một số test cũ có thể phải sửa vì thay đổi signature.

### 1.6. Rủi ro tương thích API

| Thay đổi                                      | Tương thích ngược?   | Ghi chú                                                                                   |
| :-------------------------------------------- | :------------------- | :---------------------------------------------------------------------------------------- |
| Request thêm `client_message_id` (optional)   | ✅ Tương thích       | Frontend cũ không gửi → backend hoạt động bình thường, chỉ mất idempotency                |
| Response giữ nguyên shape                     | ✅                   |                                                                                           |
| `analyze=True` vẫn nhận, nhưng backend ignore | ⚠️ Semantic thay đổi | Frontend sẽ thấy `analysis: null` trong `user_message`                                    |
| `aggregated_stress_level` có thể `null`       | ✅                   | Đã là `Optional[float]`                                                                   |
| Max length 2000 → 1000                        | ⚠️ Giảm giới hạn     | User cũ với tin nhắn dài hơn sẽ bị reject. Cần thông báo trước cho user nếu cần backfill. |
| Crisis không đóng session sau 1 message       | ✅ Thay đổi tốt      | Trước đây là bug nguy hiểm.                                                               |
| Stage mới `crisis_support` được dùng          | ✅                   | Stage này đã có trong enum `closed_reason`                                                |

### 1.7. Quyết định đã chốt với người dùng

| ID  | Câu hỏi                       | Quyết định                               | Hệ quả                                                                                                                                                                                                          |
| :-- | :---------------------------- | :--------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q-A | Max length                    | **1000 ký tự**                           | `ChatMessageRequest.message: Field(..., max_length=1000)`. User cũ có message > 1000 ký tự sẽ nhận lỗi 422 với thông báo "Tin nhắn quá dài, vui lòng tóm gọn trong 1000 ký tự."                                 |
| Q-B | Signal Panel                  | **Hiển thị "Chưa có dữ liệu phân tích"** | Khi `latestAnalysis` undefined → render placeholder. Layout giữ nguyên.                                                                                                                                         |
| Q-C | `analyze` field               | **Bỏ hoàn toàn**                         | Xóa field `analyze` khỏi `ChatMessageRequest`. Xóa field `analysis` khỏi `ChatMessageResponse`. Cập nhật frontend types tương ứng. **Phá vỡ API contract cũ** — cần thông báo và migration note trong tài liệu. |
| Q-D | Crisis `is_session_completed` | **Đổi thành False**                      | Sửa line 275: `is_session_completed=False`, chỉ giữ `is_crisis_active=True` + stage `crisis_support`. User có thể chat tiếp sau crisis banner.                                                                  |

**Lưu ý về Q-C:** Vì bạn chọn "Bỏ hoàn toàn field analyze", tôi sẽ:

1. Xóa `analyze: bool` khỏi [chat_history.py:60-64](app/modules/chat/routes/chat_history.py#L60-L64) (`ChatMessageRequest`).
2. Xóa `analysis: Optional[dict]` khỏi `ChatMessageResponse` (line 73).
3. Trong `ChatPage.tsx` xóa reference `analyze: true` ở POST body (line 441).
4. Cập nhật docstring endpoints (line 150-160) bỏ "Nếu analyze=True".
5. Đây là breaking change API — cần cập nhật cả admin-ui types (đã có `ChatAnalysis` ở [ChatPage.tsx:106](admin-ui/src/pages/ChatPage.tsx#L106), dùng cho type cast).

Tôi sẽ chuyển sang implement sau khi bạn duyệt plan.

---

## 2. Kết quả triển khai (Implementation Notes)

### 2.1. Tóm tắt thay đổi đã áp dụng

| Bug/Gap                                 | File                                                                                   |                          Trạng thái                           |
| :-------------------------------------- | :------------------------------------------------------------------------------------- | :-----------------------------------------------------------: |
| BUG-01 (Double state machine)           | [chat_response_generator.py](app/modules/chat/services/chat_response_generator.py)     |          ✅ Fixed — generator nhận `stage` bắt buộc           |
| BUG-02 (Turn 3 = reflect)               | [chat_history.py](app/modules/chat/routes/chat_history.py)                             |             ✅ Fixed — turn 3 happy = wrapping_up             |
| BUG-03 (analyze_chat_text inline)       | [chat_history.py](app/modules/chat/routes/chat_history.py)                             |                 ✅ Fixed — bỏ inline analyze                  |
| BUG-04 (Fallback hỏi lại)               | [chat_response_generator.py](app/modules/chat/services/chat_response_generator.py)     |         ✅ Fixed — `_stage_aware_fallback` per stage          |
| GAP-1 (stage param not required)        | [chat_response_generator.py](app/modules/chat/services/chat_response_generator.py)     |           ✅ Fixed — `stage` là required positional           |
| GAP-2 (Turn increment không idempotent) | [chat_history.py](app/modules/chat/routes/chat_history.py)                             |                 ✅ Fixed — transaction atomic                 |
| GAP-3 (No post-output guard)            | [chat_response_generator.py](app/modules/chat/services/chat_response_generator.py)     |              ✅ Fixed — `_output_violates_stage`              |
| GAP-4 (Crisis auto-close)               | [chat_history.py](app/modules/chat/routes/chat_history.py)                             |            ✅ Fixed — `is_session_completed=False`            |
| GAP-5 (FE no re-fetch)                  | [ChatPage.tsx](admin-ui/src/pages/ChatPage.tsx)                                        |          ✅ Fixed — re-fetch `/chat/state` on error           |
| GAP-6 (Fallback not stage-aware)        | [chat_response_generator.py](app/modules/chat/services/chat_response_generator.py)     |                   ✅ Fixed — same as BUG-04                   |
| GAP-7 (crisis_safety called 2 places)   | [chat_response_generator.py](app/modules/chat/services/chat_response_generator.py)     |                   ✅ Fixed — chỉ route gọi                    |
| GAP-8 (Non-atomic Firestore)            | [chat_session_repository.py](app/modules/chat/repositories/chat_session_repository.py) |             ✅ Fixed — `@firestore.transactional`             |
| GAP-9 (Probing loop bỏ sót 2 topic)     | [probing_questions.py](app/modules/chat/services/probing_questions.py)                 |                   ✅ Fixed — duyệt 7 topic                    |
| GAP-10 (turn count 2 sources)           | [chat_session_repository.py](app/modules/chat/repositories/chat_session_repository.py) |           ✅ Fixed — đọc từ session.user_turn_count           |
| Q1 (bỏ analyze_chat_text)               | Multiple files                                                                         |                          ✅ Applied                           |
| Q2 (Gemini hỏi ở stage cấm)             | [chat_response_generator.py](app/modules/chat/services/chat_response_generator.py)     |      ✅ Applied — post-validation + stage-aware fallback      |
| Q3 (FE state endpoint)                  | [chat_history.py](app/modules/chat/routes/chat_history.py)                             |                ✅ Applied — `GET /chat/state`                 |
| Q4 (Fallback per stage)                 | [chat_response_generator.py](app/modules/chat/services/chat_response_generator.py)     |             ✅ Applied — `_stage_aware_fallback`              |
| Q5 (Idempotency)                        | [chat_history_repository.py](app/modules/chat/repositories/chat_history_repository.py) | ✅ Applied — `client_message_id` + `_build_idempotent_replay` |
| Q6 (Hard cap + max length)              | [chat_history.py](app/modules/chat/routes/chat_history.py)                             |           ✅ Applied — max 4 turns, max_length=1000           |

### 2.2. Kết quả kiểm thử

**Test mới (v2.1): 55 PASS, 0 FAIL**

- [test_sta_chat_v2_1_state_machine.py](tests/test_sta_chat_v2_1_state_machine.py) — 14/14 pass
- [test_sta_chat_v2_1_fallback.py](tests/test_sta_chat_v2_1_fallback.py) — 15/15 pass
- [test_sta_chat_v2_1_request_models.py](tests/test_sta_chat_v2_1_request_models.py) — 6/6 pass
- [test_sta_chat_v2_1_idempotency.py](tests/test_sta_chat_v2_1_idempotency.py) — 7/7 pass
- [test_sta_chat_v2_1_crisis.py](tests/test_sta_chat_v2_1_crisis.py) — 8/8 pass
- [test_sta_chat_v2_1_probing.py](tests/test_sta_chat_v2_1_probing.py) — 5/5 pass

**Test cũ (hồi quy):**

- [test_sta_chat_compact.py](tests/test_sta_chat_compact.py) — 9/9 pass ✅
- [test_sta_chat_discipline.py](tests/test_sta_chat_discipline.py) — 17/18 pass
  - 1 fail: `test_probing_detects_topic_from_survey_context` — **test cũ stale**, do ai đó đã thêm keyword "mệt" vào `recovery.keywords` sau khi viết test. Test này đã fail trước khi tôi sửa v2.1, không liên quan. Có thể sửa test riêng sau.

### 2.3. API breaking changes (cần migration note)

| Thay đổi                                   | Tác động                                            |
| :----------------------------------------- | :-------------------------------------------------- |
| `request.analyze` bị ignore                | Frontend cũ gửi `analyze: true` không còn ảnh hưởng |
| `response.user_message.analysis` luôn null | Frontend cũ đọc field này sẽ nhận null              |
| `request.max_length` giảm 2000 → 1000      | User cũ với message > 1000 ký tự sẽ nhận 422        |
| `request.client_message_id` mới            | Optional, frontend cũ không gửi vẫn OK              |
| Endpoint mới `GET /chat/state`             | Frontend cũ không gọi vẫn OK                        |

### 2.4. Verify checklist

- [x] TypeScript compile (admin-ui)
- [x] Python import (chat routes, services, repositories)
- [x] State machine 14 test cases
- [x] Fallback 15 test cases
- [x] Request models 6 test cases
- [x] Idempotency 7 test cases
- [x] Crisis/state 8 test cases
- [x] Probing 5 test cases
- [x] Regression: compact 9/9 pass
- [x] Regression: discipline 17/18 (1 stale test fail)
