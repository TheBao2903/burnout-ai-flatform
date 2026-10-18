"""
==============================================================
File: industry_archetypes.py

12 Nhóm Ngành Chuẩn Hóa & Bối Cảnh Nghề Nghiệp Đặc Thù cho AI
==============================================================
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class IndustryArchetype:
    code: str
    name: str
    icon: str
    typical_roles: List[str]
    keywords: List[str]
    primary_burnout_mechanics: str
    vocabulary_hints: List[str]
    stressors_context: str
    reflection_theme: str


INDUSTRY_REGISTRY: Dict[str, IndustryArchetype] = {
    "tech": IndustryArchetype(
        code="tech",
        name="Công nghệ & Kỹ thuật",
        icon="💻",
        typical_roles=["Software Developer", "Frontend/Backend Engineer", "DevOps", "Data Scientist", "AI Engineer", "QA/Tester", "IT Support", "Lập trình viên", "Kỹ sư phần mềm"],
        keywords=["developer", "dev", "engineer", "software", "code", "coder", "frontend", "backend", "fullstack", "devops", "data", "ai", "tester", "qa", "qc", "it", "lập trình", "kỹ sư"],
        primary_burnout_mechanics="Cognitive Overload (quá tải nhận thức logic liên tục), Context Switching giữa nhiều task/PR, On-call và áp lực release.",
        vocabulary_hints=["sương mù não (brain fog)", "sprint/release dồn dập", "fix bug sự cố", "on-call ngắt quãng", "áp lực màn hình kéo dài"],
        stressors_context="Áp lực bàn giao sprint, lỗi phát sinh ngoài giờ, họp dự án liên miên và thời gian dài nhìn màn hình.",
        reflection_theme="Bạn có thấy việc liên tục xử lý lỗi logic khiến tâm trí khó 'tắt nguồn' vào ban đêm không?",
    ),
    "sales": IndustryArchetype(
        code="sales",
        name="Kinh doanh & Bán hàng",
        icon="💼",
        typical_roles=["Sales Representative", "Account Executive", "Business Development", "Customer Success", "Telesales", "Nhân viên kinh doanh", "Bán hàng"],
        keywords=["sales", "business development", "bd", "account", "am", "ae", "telesales", "kinh doanh", "bán hàng", "chốt sale", "tư vấn bán hàng"],
        primary_burnout_mechanics="Emotional Labor (bào mòn cảm xúc khi phải luôn vui vẻ), Target Anxiety (lo âu về số liệu KPI và hoa hồng).",
        vocabulary_hints=["bào mòn cảm xúc", "chỉ tiêu doanh số / KPI", "xử lý từ chối / khiếu nại", "luôn sẵn sàng nghe máy", "chu kỳ chốt số cuối tháng"],
        stressors_context="Áp lực doanh số cuối tháng, giao tiếp dày đặc với khách hàng khó tính, khó ngắt kết nối với điện thoại/tin nhắn.",
        reflection_theme="Việc phải duy trì vẻ ngoài nhiều năng lượng trước khách hàng có đang khiến bạn cảm thấy cạn kiệt khi trở về nhà?",
    ),
    "finance": IndustryArchetype(
        code="finance",
        name="Tài chính & Kế toán",
        icon="💰",
        typical_roles=["Accountant", "Auditor", "Financial Analyst", "Banker", "Tax Specialist", "Kế toán", "Kiểm toán", "Ngân hàng"],
        keywords=["accountant", "accounting", "auditor", "audit", "finance", "banker", "banking", "tax", "kế toán", "kiểm toán", "tài chính", "ngân hàng", "thuế", "thủ quỹ"],
        primary_burnout_mechanics="Precision Stress (áp lực độ chính xác tuyệt đối, rủi ro sai sót tiền bạc), Seasonal Spikes (quá tải cực đoan theo kỳ chốt sổ).",
        vocabulary_hints=["mùa quyết toán / chốt sổ", "đối soát chứng từ", "áp lực không được phép sai số", "ngồi lì với bảng tính số liệu"],
        stressors_context="Mùa kiểm toán và quyết toán thuế, áp lực cân đối sổ sách từng đồng, ít vận động thể chất.",
        reflection_theme="Áp lực phải tuyệt đối chính xác trong các con số có đang làm bạn căng cứng thần kinh ngay cả khi đã rời văn phòng?",
    ),
    "marketing": IndustryArchetype(
        code="marketing",
        name="Marketing & Truyền thông",
        icon="📣",
        typical_roles=["Marketing Executive", "Content Creator", "PR Specialist", "Performance Ads", "Social Media Manager", "Truyền thông", "Quảng cáo"],
        keywords=["marketing", "content", "pr", "media", "copywriter", "ads", "seo", "truyền thông", "quảng cáo", "sáng tạo nội dung"],
        primary_burnout_mechanics="Idea Depletion (cạn kiệt cảm hứng sáng tạo), Realtime Algorithm Anxiety (căng thẳng theo dõi tương tác, drama, trend số liệu).",
        vocabulary_hints=["cạn kiệt ý tưởng (creative block)", "chạy đua theo trend", "áp lực chỉ số reach/traffic", "bám sát chiến dịch campaign"],
        stressors_context="Chiến dịch chạy liên tục, áp lực tạo nội dung mới mỗi ngày, tâm trí luôn bị cuốn vào mạng xã hội.",
        reflection_theme="Việc liên tục phải nghĩ ra cái mới và bám theo thuật ngữ xu hướng có đang khiến bạn thiếu thời gian tĩnh lặng cho bản thân?",
    ),
    "design": IndustryArchetype(
        code="design",
        name="Thiết kế & Nghệ thuật",
        icon="🎨",
        typical_roles=["UI/UX Designer", "Graphic Designer", "Visual Artist", "Video Editor", "Photographer", "Thiết kế đồ họa"],
        keywords=["designer", "ui", "ux", "graphic", "artist", "illustrator", "editor", "photographer", "thiết kế", "đồ họa"],
        primary_burnout_mechanics="Subjective Feedback Fatigue (mệt mỏi vì góp ý cảm tính), Revision Loops (vòng lặp sửa thiết kế làm mất quyền tự chủ nghệ thuật).",
        vocabulary_hints=["vòng lặp revision", "feedback cảm tính", "mỏi mắt / đau cổ vai gáy", "chỉnh sửa từng pixel", "mất cảm hứng thẩm mỹ"],
        stressors_context="Khách hàng hoặc quản lý yêu cầu chỉnh sửa liên tục, thẩm mỹ bất đồng, công việc ngồi yên hàng giờ trước màn hình đồ họa.",
        reflection_theme="Những vòng lặp chỉnh sửa theo cảm tính người khác có đang dần lấy đi niềm vui sáng tạo ban đầu của bạn?",
    ),
    "healthcare": IndustryArchetype(
        code="healthcare",
        name="Y tế & Chăm sóc sức khỏe",
        icon="🏥",
        typical_roles=["Doctor", "Nurse", "Pharmacist", "Medical Technician", "Therapist", "Bác sĩ", "Điều dưỡng", "Y tá", "Dược sĩ"],
        keywords=["doctor", "nurse", "physician", "pharmacist", "medical", "hospital", "clinic", "bác sĩ", "điều dưỡng", "y tá", "dược sĩ", "y tế", "bệnh viện"],
        primary_burnout_mechanics="Compassion Fatigue (quá tải vì chứng kiến nỗi đau bệnh nhân), Circadian Disruption (trực ca kíp đêm đảo lộn đồng hồ sinh học).",
        vocabulary_hints=["trực ca kíp / đổi ca đêm", "quá tải sự thấu cảm (compassion fatigue)", "trách nhiệm an toàn sinh mạng", "bữa ăn vội vã"],
        stressors_context="Trực cấp cứu ban đêm, gánh nặng trách nhiệm tính mạng, thiếu ngủ sinh học và áp lực từ người nhà bệnh nhân.",
        reflection_theme="Sau những giờ dốc lòng chăm sóc người bệnh, bạn đã dành lại được chút thời gian nào để cơ thể mình được chăm sóc chưa?",
    ),
    "education": IndustryArchetype(
        code="education",
        name="Giáo dục & Đào tạo",
        icon="📚",
        typical_roles=["Teacher", "Lecturer", "Instructor", "Academic Tutor", "Giáo viên", "Giảng viên", "Gia sư"],
        keywords=["teacher", "lecturer", "professor", "tutor", "instructor", "academic", "giáo viên", "giảng viên", "dạy học", "đào tạo"],
        primary_burnout_mechanics="Vocal & Physical Strain (nói nhiều, đứng nhiều), Emotional Regulation với học viên, Hidden Workload (chấm bài, soạn giáo án ngoài giờ).",
        vocabulary_hints=["cháy giáo án", "chấm bài đêm", "áp lực kỳ thi / phụ huynh", "công việc không tên ngoài giờ lên lớp", "khản tiếng"],
        stressors_context="Khối lượng việc ngoài giờ lên lớp (soạn bài, chấm điểm), áp lực quản lý lớp học và kỳ vọng từ phụ huynh/nhà trường.",
        reflection_theme="Các công việc chuẩn bị bài vở ngoài giờ có đang âm thầm xâm chiếm buổi tối thư giãn bên gia đình của bạn?",
    ),
    "legal_public": IndustryArchetype(
        code="legal_public",
        name="Pháp lý & Hành chính công",
        icon="⚖️",
        typical_roles=["Lawyer", "Legal Counsel", "Civil Servant", "Compliance Officer", "Luật sư", "Pháp chế", "Công chức"],
        keywords=["lawyer", "legal", "counsel", "compliance", "civil servant", "government", "luật sư", "pháp chế", "pháp lý", "công chức", "hành chính"],
        primary_burnout_mechanics="Procedural Rigidity (áp lực thủ tục nghiêm ngặt), High Liability Anxiety (lo sợ rủi ro vi phạm pháp lý/chế tài).",
        vocabulary_hints=["rà soát điều khoản dày đặc", "áp lực tuân thủ (compliance)", "thủ tục giấy tờ hành chính", "tâm thế phòng vệ rủi ro"],
        stressors_context="Hồ sơ văn bản pháp lý phức tạp, căng thẳng đối tụng hoặc xử lý tranh chấp, trách nhiệm cao trước pháp luật.",
        reflection_theme="Việc luôn phải ở tâm thế cảnh giác và phòng vệ rủi ro có đang khiến tâm trí bạn khó thả lỏng ngay cả khi nghỉ ngơi?",
    ),
    "production": IndustryArchetype(
        code="production",
        name="Sản xuất & Vận hành",
        icon="🏭",
        typical_roles=["Factory Engineer", "Plant Operator", "Technician", "QA Inspector", "Kỹ sư sản xuất", "Vận hành máy", "Nhà xưởng"],
        keywords=["factory", "production", "plant", "operator", "technician", "assembly", "manufacture", "sản xuất", "nhà máy", "nhà xưởng", "vận hành"],
        primary_burnout_mechanics="Physical Strain (đứng lâu, tiếng ồn nhà máy), Monotonous Alertness (lặp đi lặp lại nhưng vẫn phải đảm bảo an toàn tuyệt đối).",
        vocabulary_hints=["tiếng ồn nhà xưởng", "áp lực định mức sản lượng", "đảm bảo an toàn lao động", "mỏi cơ bắp sau ca làm", "xoay ca ngày đêm"],
        stressors_context="Môi trường nhà xưởng tiếng ồn, đứng lâu trên dây chuyền, áp lực chỉ tiêu sản lượng và định mức lỗi sản phẩm.",
        reflection_theme="Cơ thể bạn có đang phát đi những tín hiệu mệt mỏi cơ bắp và đau nhức cần được kéo giãn sau ca làm không?",
    ),
    "services_logistics": IndustryArchetype(
        code="services_logistics",
        name="Dịch vụ, Du lịch & Logistics",
        icon="🚚",
        typical_roles=["Hotel Staff", "Restaurant Staff", "Driver", "Warehouse Operator", "Logistics Coordinator", "Nhân viên nhà hàng", "Tài xế", "Kho vận"],
        keywords=["hotel", "restaurant", "hospitality", "tourism", "driver", "courier", "logistics", "warehouse", "giao hàng", "tài xế", "nhà hàng", "khách sạn", "kho vận"],
        primary_burnout_mechanics="Irregular Circadian Rhythm (giờ ăn ngủ thất thường theo khách/chuyến xe), High Paced Responsiveness (xử lý tức thì).",
        vocabulary_hints=["ăn uống lệch giờ", "áp lực giao hàng đúng hẹn", "đứng hoặc lái xe nhiều giờ", "xử lý sự cố dịch vụ phát sinh"],
        stressors_context="Thời gian biểu thất thường, áp lực thời gian giao nhận, phục vụ khách hàng liên tục trong môi trường gấp gáp.",
        reflection_theme="Nhịp độ sinh hoạt không cố định dạo gần đây có đang ảnh hưởng đến chất lượng các bữa ăn và giấc ngủ của bạn?",
    ),
    "science_research": IndustryArchetype(
        code="science_research",
        name="Khoa học & Nghiên cứu",
        icon="🔬",
        typical_roles=["Researcher", "Scientist", "Lab Specialist", "R&D Engineer", "Nghiên cứu viên", "Chuyên viên R&D"],
        keywords=["researcher", "scientist", "research", "lab", "r&d", "phd", "postdoc", "nghiên cứu", "thí nghiệm", "khoa học"],
        primary_burnout_mechanics="Outcome Ambiguity (thí nghiệm thất bại liên tiếp), Long-cycle Isolation (công việc độc lập, dự án dài hạn ít phản hồi tích cực).",
        vocabulary_hints=["thử nghiệm bế tắc", "áp lực tiến độ đề tài", "sự cô độc trong phòng nghiên cứu", "dữ liệu không như kỳ vọng"],
        stressors_context="Thí nghiệm không ra kết quả, áp lực bài báo và bảo vệ đề tài, chu kỳ công việc kéo dài mà thiếu ghi nhận tức thì.",
        reflection_theme="Cảm giác tiến độ nghiên cứu chậm dạo này có đang làm bạn mất dần ngọn lửa đam mê ban đầu?",
    ),
    "construction_realestate": IndustryArchetype(
        code="construction_realestate",
        name="Xây dựng, Kiến trúc & Bất động sản",
        icon="🏗️",
        typical_roles=["Architect", "Site Engineer", "Project Supervisor", "Real Estate Agent", "Kiến trúc sư", "Kỹ sư công trường", "Giám sát xây dựng", "Môi giới BĐS"],
        keywords=["architect", "construction", "site", "civil", "real estate", "property", "xây dựng", "công trường", "kiến trúc", "bất động sản", "môi giới"],
        primary_burnout_mechanics="Dual Physical-Mental Strain (nắng gió công trường + áp lực tiến độ bàn giao), Conflict Management (áp lực từ chủ đầu tư, cai thầu).",
        vocabulary_hints=["áp lực tiến độ công trường", "nắng gió hiện trường", "thay đổi thiết kế đột xuất", "xử lý mâu thuẫn thầu phụ"],
        stressors_context="Di chuyển hiện trường dưới thời tiết khắc nghiệt, áp lực mốc hoàn thành công trình, thương lượng lợi ích giữa nhiều bên.",
        reflection_theme="Sự kết hợp giữa áp lực tiến độ bàn giao và việc di chuyển hiện trường có đang làm bạn quá tải cả sức khỏe lẫn tinh thần?",
    ),
}

DEFAULT_ARCHETYPE = IndustryArchetype(
    code="general_office",
    name="Văn phòng & Chuyên môn tổng quát",
    icon="🏢",
    typical_roles=["Nhân viên văn phòng", "Quản lý", "Chuyên viên"],
    keywords=[],
    primary_burnout_mechanics="Khối lượng công việc dồn dập, áp lực thời hạn và sự cân bằng giữa làm việc và nghỉ ngơi.",
    vocabulary_hints=["áp lực tiến độ", "khối lượng việc dồn", "thiếu thời gian tái tạo năng lượng"],
    stressors_context="Áp lực hoàn thành công việc đúng hạn, cân bằng giữa trách nhiệm và thời gian cá nhân.",
    reflection_theme="Bạn có nhận thấy khối lượng công việc gần đây đang làm giảm đi thời gian dành cho chính mình?",
)


def resolve_industry_context(
    industry_code: Optional[str] = None,
    job_title: Optional[str] = None,
) -> IndustryArchetype:
    """Tự động phân loại ngành nghề dựa trên industry_code hoặc job_title."""
    if industry_code and industry_code in INDUSTRY_REGISTRY:
        return INDUSTRY_REGISTRY[industry_code]

    if job_title and isinstance(job_title, str):
        title_lower = job_title.lower().strip()
        for code, arch in INDUSTRY_REGISTRY.items():
            for kw in arch.keywords:
                if kw in title_lower:
                    return arch

    return DEFAULT_ARCHETYPE
