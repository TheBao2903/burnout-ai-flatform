"""
==============================================================
File: knowledge.py

Knowledge Models - Tri thuc cho RAG.
==============================================================
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class InsightResult(BaseModel):
    """Nhan dinh chi tiet ve burnout."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "insight_001",
                "session_id": "session_abc123",
                "summary": "Nguoi dung co dau hieu thieu ngu...",
                "primary_factor": "sleep",
                "secondary_factor": "workload",
                "stress_level": "high",
                "burnout_risk": "high",
                "confidence": 0.85
            }
        }
    )

    id: str = Field(..., description="Unique ID")
    session_id: str = Field(..., description="ID cua session")
    summary: str = Field(..., description="Tom tat nhan dinh")
    primary_factor: str = Field(..., description="Factor chinh")
    secondary_factor: str = Field(..., description="Factor phu")
    stress_level: Literal["low", "medium", "high"] = Field(..., description="Muc do stress")
    burnout_risk: Literal["low", "medium", "high"] = Field(..., description="Rui ro burnout")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Do tin cay")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem tao")


class KnowledgeDocument(BaseModel):
    """Tri thuc da duoc chuan hoa."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "know_001",
                "source": "user_session",
                "document_type": "burnout_case",
                "title": "Case: Sleep Deprivation",
                "content": "Nguoi dung ngu 4-5 tieng...",
                "keywords": ["sleep", "workload", "burnout"],
                "tags": ["sleep", "workload"],
                "language": "vi"
            }
        }
    )

    id: str = Field(..., description="Unique ID")
    source: Literal["who", "apa", "user_session", "research_paper", "recommendation", "system"] = Field(..., description="Nguon goc")
    document_type: Literal["burnout_case", "knowledge", "recommendation", "guideline", "research"] = Field(..., description="Loai document")
    title: str = Field(..., description="Tieu de")
    content: str = Field(..., description="Noi dung")
    keywords: List[str] = Field(default_factory=list, description="Tu khoa")
    tags: List[str] = Field(default_factory=list, description="Tags")
    language: str = Field(default="vi", description="Ngon ngu: vi, en")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem tao")


class VectorPayload(BaseModel):
    """Payload luu trong Qdrant."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "point_id": "point_001",
                "knowledge_id": "know_001",
                "collection_name": "burnout_knowledge",
                "payload": {"title": "Case Study", "keywords": ["sleep"]},
                "created_at": "2024-01-20T10:16:00Z"
            }
        }
    )

    point_id: str = Field(..., description="ID cua point trong Qdrant")
    knowledge_id: str = Field(..., description="ID cua KnowledgeDocument")
    collection_name: Literal["burnout_knowledge", "burnout_case_memory", "recommendations"] = Field(..., description="Ten collection")
    payload: Dict = Field(..., description="Metadata payload")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem tao")
