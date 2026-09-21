"""
==============================================================
Module: User

Chuc nang:
- User Profile management
- View and update profile

 Cau truc:
- models/     - Pydantic DTOs
- services/   - Business logic
- repositories/ - Firestore operations
- routes/     - API endpoints
==============================================================
"""

from app.modules.user.routes import router

__all__ = ["router"]
