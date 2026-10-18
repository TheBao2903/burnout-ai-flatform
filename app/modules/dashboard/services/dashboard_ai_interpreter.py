"""
==============================================================
File: dashboard_ai_interpreter.py

DashboardAIInterpreter - Tầng 3 (AI Qualitative Synthesis) cho Dashboard.

Nhiệm vụ:
- Tổng hợp dữ liệu đa ngày (7-30 ngày) kết hợp giữa:
  + Tín hiệu đo lường khách quan STA Core & Context
  + 12 Nhóm ngành nghề chuẩn hóa (Industry Archetypes)
  + 6 Hình mẫu tổ hợp năng lượng chéo (Cross-Metric Archetypes)
- Sử dụng Gemini API sinh Nhận Định Bối Cảnh Thực Tế cá nhân hóa, thấu cảm.
- Tuyệt đối KHÔNG đọc lại con số khô khan.
- Trả về JSON: {"summary": "...", "key_observations": [...]}
- Fallback tự động, mượt mà, đậm chất chuyên môn nếu offline hoặc chưa có API key.
==============================================================
"""

import concurrent.futures
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("burnout.dashboard.interpreter")

SYSTEM_PROMPT = """Bạn là một Chuyên gia Cố vấn Sức khỏe Tinh thần Nơi Làm Việc (Workplace Wellbeing Companion & Advisor) ấm áp, sâu sắc và tinh tế.
Nhiệm vụ của bạn là nhận các bằng chứng tổng hợp đa chiều về công việc, giấc ngủ và năng lượng của người dùng trong khoảng thời gian vừa qua để viết ra "Nhận Định Bối Cảnh Thực Tế Từ Hệ Thống" (Synthesized Insight).

NGUYÊN TẮC BẮT BUỘC:
1. TUYỆT ĐỐI KHÔNG ĐỌC LẠI CON SỐ/CHỈ SỐ HAY PHẦN TRĂM KHÔ KHAN (Ví dụ KHÔNG nói "Chỉ số cạn kiệt là 3.2/5", "Bạn quá tải 3/5 lần", "Giấc ngủ trung bình 5.5h", vì toàn bộ các con số này người dùng đã thấy rất rõ ở các thẻ và biểu đồ phía trên).
2. DỊCH DỮ LIỆU THÀNH BỨC TRANH THỰC TẾ: Hãy miêu tả nhịp độ làm việc, xu hướng tích tụ mệt mỏi, sự cân bằng giữa tiêu hao năng lượng và cơ hội tái tạo sức lực theo cách diễn đạt đời thường, tự nhiên và thấu cảm.
3. TẬP TRUNG VÀO ĐẶC THÙ NGÀNH NGHỀ & HÌNH MẪU NĂNG LƯỢNG CỦA NGƯỜI DÙNG: Vận dụng đúng thuật ngữ và bối cảnh công việc thực tế của ngành nghề được cung cấp.
4. KHÔNG CHẨN ĐOÁN Y KHOA: Không phán xét "Bạn bị kiệt sức hoàn toàn/trầm cảm".
5. KHÔNG KHẲNG ĐỊNH NGUYÊN NHÂN NHÂN QUẢ TUYỆT ĐỐI: Dùng các từ ngữ "có thể liên quan đến", "dường như đang là yếu tố chính", "cho thấy nhu cầu nghỉ ngơi đang gia tăng".
6. ĐỊNH DẠNG ĐẦU RA JSON BẮT BUỘC (Trả về duy nhất 1 JSON object, không có markdown code fence thừa):
{
  "summary": "2-3 câu văn tự nhiên, thấu cảm, đúc kết bức tranh tổng thể về nhịp điệu làm việc và năng lượng của người dùng trong suốt kỳ theo dõi gắn liền với ngành nghề của họ.",
  "key_observations": [
    "Quan sát trọng yếu 1 (chỉ rõ sự ảnh hưởng của đặc thù nghề nghiệp đến năng lượng)",
    "Quan sát trọng yếu 2 (về xu hướng thay đổi năng lượng và khả năng hồi phục)",
    "Quan sát trọng yếu 3 (nếu có, tối đa 4 quan sát)"
  ]
}
"""


class DashboardAIInterpreter:
    """Service chịu trách nhiệm phân tích định tính toàn diện cho Dashboard bằng Gemini."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: float = 1800.0  # 30 phút TTL
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="DashboardAI")

    def _compute_cache_key(self, evidence: Dict[str, Any]) -> str:
        """Tạo khóa hash MD5 duy nhất cho tập bằng chứng."""
        try:
            evidence_str = json.dumps(evidence, sort_keys=True, default=str)
        except Exception:
            evidence_str = str(sorted(evidence.items()))
        return hashlib.md5(evidence_str.encode("utf-8")).hexdigest()

    def _get_gemini(self) -> Optional[Any]:
        """Khởi tạo Gemini Client một cách lười (lazy load)."""
        if self._client is not None:
            return self._client

        from app.core.settings import get_settings
        settings = get_settings().google_ai
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or settings.api_key
        if not api_key:
            logger.warning("GEMINI_API_KEY is not set. DashboardAIInterpreter will use fallback.")
            return None

        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
            return self._client
        except Exception as e:
            logger.error("Failed to initialize Google GenAI Client for Dashboard: %s", e)
            return None

    def _call_gemini_raw(self, evidence: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Thực thi gọi Gemini qua GeminiRotator."""
        from app.core.gemini_rotator import get_gemini_rotator
        rotator = get_gemini_rotator()
        prompt = self._build_prompt(evidence)

        def _execute(client, model):
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "temperature": 0.75,
                    "response_mime_type": "application/json",
                },
            )

        response, model_used, key_used = rotator.execute_with_failover(_execute)

        if hasattr(response, "text") and response.text:
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1] if "```" in text else text
                text = text.lstrip("json").strip()
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()
            data = json.loads(text)
            summary = data.get("summary", "").strip()
            key_obs = data.get("key_observations", [])
            if isinstance(key_obs, list) and summary:
                return {
                    "summary": summary,
                    "key_observations": [str(item).strip() for item in key_obs if str(item).strip()],
                }
        return None

    def generate_synthesized_insight(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Sinh nhận định bối cảnh tổng hợp từ các tín hiệu đo lường với Cache & Fast Timeout."""
        now = time.time()
        cache_key = self._compute_cache_key(evidence)

        # 1. Kiểm tra In-Memory Cache
        cached_entry = self._cache.get(cache_key)
        if cached_entry and (now - cached_entry["timestamp"] < self._cache_ttl):
            logger.debug("Dashboard AI Synthesized Insight cache hit (key=%s)", cache_key[:8])
            return cached_entry["data"]

        # Dọn dẹp cache nếu quá đầy
        if len(self._cache) > 200:
            expired_keys = [k for k, v in self._cache.items() if now - v["timestamp"] >= self._cache_ttl]
            for k in expired_keys:
                self._cache.pop(k, None)

        # 2. Gọi Gemini với Timeout 3.5 giây để bảo vệ trải nghiệm người dùng
        try:
            future = self._executor.submit(self._call_gemini_raw, evidence)
            result = future.result(timeout=3.5)
            if result:
                self._cache[cache_key] = {"data": result, "timestamp": now}
                return result
        except concurrent.futures.TimeoutError:
            logger.warning("Gemini Dashboard AI Synthesis timed out after 3.5s, switching to expert rule fallback")
        except Exception as e:
            logger.error("Gemini Dashboard AI Synthesis failed: %s", e)

        # 3. Trả về fallback chuẩn mực tức thì (< 1ms)
        fallback_insight = self._generate_fallback(evidence)
        # Cache fallback ngắn hạn (60s) để tránh spam request liên tục nếu API đang down
        self._cache[cache_key] = {"data": fallback_insight, "timestamp": now - self._cache_ttl + 60.0}
        return fallback_insight

    def _build_prompt(self, evidence: Dict[str, Any]) -> str:
        """Tạo prompt giàu ngữ cảnh nghề nghiệp và hình mẫu năng lượng."""
        days = evidence.get("days", 30)
        n = evidence.get("total_checkins", 0)
        ex_level = evidence.get("exhaustion_level", "trung bình")
        ex_trend = evidence.get("exhaustion_trend", "ổn định")
        dis_level = evidence.get("disengagement_level", "trung bình")
        dis_trend = evidence.get("disengagement_trend", "ổn định")
        rec_status = evidence.get("recovery_status", "trung bình")
        overload_count = evidence.get("overload_count", 0)
        top_reasons = evidence.get("top_reasons", [])
        other_reasons = evidence.get("other_reasons", [])
        ot_hours = evidence.get("ot_hours_total", 0.0)
        ot_days = evidence.get("ot_days_count", 0)

        # Ngữ cảnh ngành nghề & hình mẫu năng lượng
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

BẰNG CHỨNG ĐO LƯỜNG TỔNG HỢP:
- Chu kỳ theo dõi: {days} ngày qua ({n} phiên check-in thực tế)
- Trạng thái cạn kiệt năng lượng: Mức độ {ex_level}, chiều hướng đang {ex_trend}
- Mức độ gắn kết công việc: Mức độ {dis_level}, chiều hướng đang {dis_trend}
- Trạng thái giấc ngủ & hồi phục buổi sáng: {rec_status}
- Tần suất quá tải: {overload_count}/{n} phiên check-in
- Các nguyên nhân quá tải nổi trội: {', '.join(top_reasons) if top_reasons else 'Không có'}
- Ghi chú thực tế từ người dùng: {', '.join(other_reasons) if other_reasons else 'Không có'}
- Khối lượng làm thêm giờ (OT): Đã có {ot_hours} giờ trong {ot_days} ngày

Hãy dựa vào các bằng chứng trên, xuất ra duy nhất 1 JSON object theo cấu trúc quy định.
"""
        return prompt

    def _generate_fallback(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo nhận định quy tắc mượt mà, bám sát ngành nghề và hình mẫu khi Gemini offline."""
        days = evidence.get("days", 30)
        ex_trend = evidence.get("exhaustion_trend", "stable")
        ex_level = evidence.get("exhaustion_level", "medium")
        overload_count = evidence.get("overload_count", 0)
        top_reasons = evidence.get("top_reasons", [])
        ot_hours = evidence.get("ot_hours_total", 0.0)
        ot_days = evidence.get("ot_days_count", 0)
        rec_status = evidence.get("recovery_status", "moderate")
        industry_name = evidence.get("industry_name", "công việc hiện tại")
        archetype_name = evidence.get("archetype_name", "")

        obs: List[str] = []
        if ex_trend == "increasing":
            obs.append("Tín hiệu cạn kiệt năng lượng có chiều hướng tăng dần trong chu kỳ theo dõi vừa qua.")
        elif ex_trend == "decreasing":
            obs.append("Năng lượng và thể trạng đang có chiều hướng hồi phục tích cực so với giai đoạn trước.")

        if overload_count > 0:
            top_reason_text = f"chủ yếu liên quan đến {top_reasons[0].lower()}" if top_reasons else ""
            obs.append(f"Ghi nhận một số thời điểm chịu tải cao {top_reason_text}.")

        if rec_status == "poor":
            obs.append("Chất lượng giấc ngủ và cảm giác hồi phục vào buổi sáng chưa thật sự bù đắp đủ năng lượng đã tiêu hao.")
        elif rec_status == "good":
            obs.append("Chất lượng giấc ngủ và khả năng tái tạo sức lực vào đầu ngày được duy trì khá tốt.")

        if ot_hours > 3.0:
            obs.append(f"Thời gian làm thêm ngoài giờ phát sinh trong {ot_days} ngày dường như đang làm thu hẹp khoảng nghỉ ngơi cá nhân.")

        if ex_level in ("high", "critical"):
            summary_text = (
                f"Trong {days} ngày vừa qua, nhịp độ trong lĩnh vực {industry_name} đang đòi hỏi nhiều sự tập trung và gắng sức, "
                f"khiến năng lượng của bạn bị hao hụt nhanh hơn bình thường. "
                + (" ".join(obs) if obs else "Cơ thể bạn đang phát đi tín hiệu cần các khoảng nghỉ ngắn để tái tạo lại sức lực.")
            )
        else:
            summary_text = (
                f"Trong {days} ngày vừa qua, nhịp làm việc và trạng thái thể chất của bạn duy trì tương đối ổn định. "
                + (" ".join(obs) if obs else "Các chỉ số bối cảnh công việc và năng lượng duy trì ở mức cân bằng tốt.")
            )

        return {
            "summary": summary_text,
            "key_observations": obs,
        }


_dashboard_interpreter_instance: Optional[DashboardAIInterpreter] = None


def get_dashboard_ai_interpreter() -> DashboardAIInterpreter:
    global _dashboard_interpreter_instance
    if _dashboard_interpreter_instance is None:
        _dashboard_interpreter_instance = DashboardAIInterpreter()
    return _dashboard_interpreter_instance
