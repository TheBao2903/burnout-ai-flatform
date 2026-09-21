"""
==============================================================
Module: Emotion

Chuc nang:
- Nhan anh tu client
- Phan tich cam xuc bang DeepFace (vendor o external/deepface/)
- Luu emotion vao Firestore
- Tuy chon luu anh len Cloudflare R2 (khi user dong y)
- Tuy chon goi AI assessment
==============================================================
"""

from app.modules.emotion.routes import router

__all__ = ["router"]