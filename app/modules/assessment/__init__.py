"""
==============================================================
Module: Assessment

Chuc nang:
- Assessment Session management
- Survey templates (cau hoi danh gia)
- AI Assessment sinh tu emotion (OpenAI)
==============================================================
"""

from app.modules.assessment.routes import assessment_session_router

# Export router cho main.py
router = assessment_session_router

__all__ = ["router", "assessment_session_router"]