"""
==============================================================
File: matrix_resolver.py

Ma Trận Tổ Hợp Chỉ Số Chéo (Cross-Metric Matrix Resolver)
Kết hợp giữa:
- 16 Câu Hỏi OLBI Định Kỳ (2 tuần - Macro/Chronic Trait)
- 8 Câu Hỏi Daily Pulse (Hàng ngày - Micro/Acute State)
Giải mã thành 6 Hình Mẫu Năng Lượng & Tâm Lý (Energy Archetypes)
==============================================================
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class BurnoutArchetype:
    code: str
    name: str
    icon: str
    summary_diagnosis: str
    psychological_mechanism: str
    empathy_direction: str
    ai_prompt_instruction: str


ARCHETYPE_DEFINITIONS: Dict[str, BurnoutArchetype] = {
    "classic_burnout": BurnoutArchetype(
        code="classic_burnout",
        name="Kiệt Sức Kinh Niên (Classic Burnout)",
        icon="🔥",
        summary_diagnosis="Hao mòn toàn diện cả thể chất lẫn tinh thần gắn kết với công việc.",
        psychological_mechanism="Cả hai trụ cột Kiệt sức (Exhaustion) và Mất gắn kết (Disengagement) đều ở ngưỡng cao kéo dài, phục hồi buổi sáng kém.",
        empathy_direction="Đồng cảm sâu sắc, nhẹ nhàng, vỗ về. Không đưa lời khuyên phức tạp hay yêu cầu cố gắng. Nhấn mạnh việc bảo toàn sức khỏe và giảm tải ngay.",
        ai_prompt_instruction="Người dùng đang trong trạng thái kiệt sức kinh niên. Hãy trò chuyện như một người bạn tri kỷ dịu dàng, thừa nhận sự mệt mỏi cùng cực của họ, khuyên họ buông bớt gánh nặng và ưu tiên nghỉ ngơi phục hồi.",
    ),
    "acute_crunch": BurnoutArchetype(
        code="acute_crunch",
        name="Bão Dự Án / Căng Thẳng Cấp Tính (Acute Crunch)",
        icon="⚡",
        summary_diagnosis="Áp lực cao độ do khối lượng và thời hạn dự án ngắn hạn, nhưng vẫn giữ được tâm huyết với công việc.",
        psychological_mechanism="Job demands và tăng ca vọt lên trong các ngày gần đây, trong khi sự gắn kết vẫn cao, kiệt sức là hệ quả của việc dồn sức ngắn hạn.",
        empathy_direction="Đồng minh chiến lược. Thừa nhận sự cống hiến vượt bậc, hướng dẫn kỹ thuật duy trì sức bền (micro-breaks) và nhắc nhở kế hoạch nghỉ bù sau khi dứt điểm dự án.",
        ai_prompt_instruction="Người dùng đang chịu tải cao trong giai đoạn nước rút nhưng tinh thần vẫn hăng say. Đừng nói họ chán việc; hãy hướng dẫn họ cách 'phanh ngắn' để không bị sụp đổ sức lực giữa chừng.",
    ),
    "boreout_disconnection": BurnoutArchetype(
        code="boreout_disconnection",
        name="Mất Kết Nối & Hoài Nghi (Boreout / Quiet Quitting)",
        icon="🧊",
        summary_diagnosis="Cơ thể không quá mệt mỏi nhưng tinh thần xa rời, cảm thấy công việc vô nghĩa hoặc thiếu động lực nội tại.",
        psychological_mechanism="Điểm Mất gắn kết (Disengagement) rất cao trong khi Kiệt sức thể chất ở mức thấp hoặc trung bình, không có áp lực tăng ca.",
        empathy_direction="Khơi gợi ý nghĩa và tự chủ. Tránh khuyên ngủ nghỉ (vì họ không thiếu ngủ), mà tập trung hỏi về sự hứng thú, giá trị đóng góp và mong muốn thử thách mới.",
        ai_prompt_instruction="Vấn đề của người dùng không phải thiếu ngủ hay việc quá nhiều, mà là sự thờ ơ và mất kết nối với ý nghĩa công việc. Hãy gợi mở để họ suy ngẫm về điều gì thực sự khiến họ có động lực.",
    ),
    "engaged_hero": BurnoutArchetype(
        code="engaged_hero",
        name="Chiến Binh Quên Mình (Engaged Hero)",
        icon="🏃",
        summary_diagnosis="Nhiệt huyết và đam mê rất cao nhưng cơ thể đang tích tụ sự suy kiệt nghiêm trọng do thiếu ngủ và không chịu dừng lại.",
        psychological_mechanism="Mất gắn kết cực thấp (yêu công việc), nhưng Kiệt sức cao, ngủ dưới 6h kéo dài, nguy cơ sụp đổ đột ngột (Sudden Crash).",
        empathy_direction="Cảnh báo chân thành và yêu thương. Khen ngợi tinh thần nhưng nhấn mạnh 'đam mê cần một thân xác khỏe mạnh để đi đường dài'.",
        ai_prompt_instruction="Người dùng yêu công việc đến mức đang bỏ quên bản thân. Hãy cảnh báo nhẹ nhàng rằng việc không chịu phanh lại chính là đang 'vay mượn sức khỏe tương lai'.",
    ),
    "physical_depletion_only": BurnoutArchetype(
        code="physical_depletion_only",
        name="Suy Kiệt Thể Chất Ngoại Cảnh (Physical Depletion)",
        icon="🌙",
        summary_diagnosis="Năng lượng thấp chủ yếu do giấc ngủ và phục hồi sinh học kém, không xuất phát từ áp lực công việc trực tiếp.",
        psychological_mechanism="Exhaustion cao, Recovery sáng rất thấp, nhưng Job demands và Disengagement ở mức bình thường, không có tăng ca.",
        empathy_direction="Thấu cảm đời sống sinh hoạt. Phân tách rõ áp lực không đến từ nơi làm việc, hướng dẫn chăm sóc giấc ngủ, dinh dưỡng và thư giãn buổi tối.",
        ai_prompt_instruction="Sự uể oải của người dùng xuất phát từ thiếu ngủ sinh học hơn là do công việc. Hãy đồng cảm với những đêm mất ngủ hoặc lịch sinh hoạt bị xáo trộn.",
    ),
    "balanced_thriving": BurnoutArchetype(
        code="balanced_thriving",
        name="Cân Bằng & Hưng Phấn (Balanced & Thriving)",
        icon="🌿",
        summary_diagnosis="Nhịp điệu làm việc hài hòa, khả năng tái tạo năng lượng tốt, duy trì được sự chủ động và thoải mái.",
        psychological_mechanism="Tất cả các chỉ số cạn kiệt và mất gắn kết đều ở vùng an toàn, giấc ngủ và điểm hồi phục buổi sáng đạt chất lượng tốt.",
        empathy_direction="Tích cực, khích lệ. Giúp người dùng nhìn nhận ra công thức sinh hoạt tích cực hiện tại để duy trì bền vững.",
        ai_prompt_instruction="Người dùng đang có trạng thái rất tốt. Hãy dành lời khen ngợi cho sự cân bằng này và khuyến khích họ duy trì thói quen hiện tại.",
    ),
}


def resolve_burnout_archetype(
    ex_score: float,
    dis_score: float,
    daily_stats: Optional[Dict[str, Any]] = None,
) -> BurnoutArchetype:
    """Xác định Hình Mẫu Năng Lượng dựa trên tổ hợp chỉ số chéo."""
    stats = daily_stats or {}
    job_demands = float(stats.get("job_demands") or stats.get("avg_jd") or 2.5)
    sleep_hours = float(stats.get("sleep_hours") or stats.get("avg_sleep") or 7.0)
    recovery_score = float(stats.get("recovery_score") or stats.get("avg_rec") or 3.0)
    ot_hours = float(stats.get("ot_hours_total") or stats.get("overtime_hours") or 0.0)
    overload_count = int(stats.get("overload_count") or (1 if stats.get("quick_overload", 0) >= 4 else 0))

    is_high_ex = ex_score >= 3.2
    is_high_dis = dis_score >= 3.0
    is_low_dis = dis_score <= 2.3
    is_poor_recovery = recovery_score <= 2.3 or sleep_hours < 6.0
    is_high_demands = job_demands >= 3.4 or ot_hours >= 4.0 or overload_count >= 1

    # 1. Classic Burnout: Both EX & DIS are high, poor recovery
    if is_high_ex and is_high_dis:
        return ARCHETYPE_DEFINITIONS["classic_burnout"]

    # 2. Engaged Hero: High EX, Very Low DIS (loves work), Poor sleep
    if is_high_ex and is_low_dis and is_poor_recovery:
        return ARCHETYPE_DEFINITIONS["engaged_hero"]

    # 3. Acute Crunch: High Demands / OT in daily, but DIS is still not high
    if is_high_demands and not is_high_dis and (is_high_ex or ot_hours >= 3.0):
        return ARCHETYPE_DEFINITIONS["acute_crunch"]

    # 4. Boreout / Disconnection: DIS is high, but EX is not high, demands normal
    if is_high_dis and not is_high_ex and not is_high_demands:
        return ARCHETYPE_DEFINITIONS["boreout_disconnection"]

    # 5. Physical Depletion Only: High EX, but DIS is low, Demands are normal/low, poor recovery
    if is_high_ex and not is_high_demands and is_poor_recovery:
        return ARCHETYPE_DEFINITIONS["physical_depletion_only"]

    # 6. Default / Balanced Thriving
    if not is_high_ex and not is_high_dis and not is_poor_recovery:
        return ARCHETYPE_DEFINITIONS["balanced_thriving"]

    # Fallback to nearest based on primary dimension
    if is_high_ex:
        return ARCHETYPE_DEFINITIONS["classic_burnout"] if is_high_dis else ARCHETYPE_DEFINITIONS["acute_crunch"]

    return ARCHETYPE_DEFINITIONS["balanced_thriving"]
