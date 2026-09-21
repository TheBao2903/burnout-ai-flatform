"""
==============================================================
File: admin_users.py

Admin User Management Routes - CRUD users cho admin.

GET  /api/auth/admin/users        - Danh sách users (paginated)
GET  /api/auth/admin/users/{id}  - Chi tiết user
PUT  /api/auth/admin/users/{id}   - Cập nhật user
DELETE /api/auth/admin/users/{id} - Xóa user
==============================================================
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.modules.auth.services.auth_service import AuthError, AuthService, get_auth_service

logger = logging.getLogger("burnout.auth.admin.users")


def _format_datetime(dt):
    """Format datetime từ Firestore (datetime, Timestamp, hoặc ISO string)."""
    import logging
    logger = logging.getLogger("burnout.auth.admin.users")

    if dt is None:
        return None

    try:
        # Handle Firestore Timestamp - check class name exactly
        type_name = type(dt).__name__
        if 'Timestamp' in type_name:
            dt = dt.to_datetime()

        # Handle string input
        if isinstance(dt, str):
            if not dt.strip():
                return None
            # Try to parse ISO format
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except:
                try:
                    from datetime import datetime as dt_parser
                    dt = dt_parser.strptime(dt, '%Y-%m-%d %H:%M:%S')
                except:
                    return dt  # Return as-is if can't parse

        # Now dt should be a datetime object
        if hasattr(dt, 'isoformat'):
            iso_str = dt.isoformat()
            # Ensure it ends with Z
            if iso_str.endswith('+00:00'):
                iso_str = iso_str[:-6] + 'Z'
            elif not iso_str.endswith('Z'):
                iso_str = iso_str + 'Z'
            return iso_str

    except Exception as e:
        logger.warning("Error formatting datetime: %s", e)

    return str(dt) if dt else None

router = APIRouter(prefix="/api/auth/admin", tags=["Admin Users"])


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Yêu cầu quyền admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


@router.get("/users")
async def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    role_filter: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    svc: AuthService = Depends(get_auth_service),
    admin: dict = Depends(require_admin),
):
    """Danh sách users (phân trang).

    Args:
        limit: Số lượng user mỗi trang (max 100)
        offset: Bắt đầu từ index nào
        role_filter: Lọc theo role (user/admin)
        search: Tìm kiếm theo username/email/full_name
    """
    from google.cloud import firestore
    from app.core.firebase import get_firebase

    db = get_firebase().db
    collection = db.collection("users")

    # Build query
    query = collection.order_by("created_at", direction=firestore.Query.DESCENDING)

    if role_filter:
        query = query.where("role", "==", role_filter)

    # Get all docs first (Firestore doesn't support full-text search)
    all_users = []
    for doc in query.stream():
        data = doc.to_dict()
        data["id"] = doc.id

        # Filter by search
        if search:
            search_lower = search.lower()
            username = data.get("username", "").lower()
            email = data.get("email", "").lower()
            full_name = data.get("full_name", "").lower()
            if not (
                search_lower in username
                or search_lower in email
                or search_lower in full_name
            ):
                continue

        all_users.append(data)

    # Sort by search relevance if searching
    if search:
        search_lower = search.lower()
        all_users.sort(
            key=lambda u: (
                0 if search_lower in u.get("username", "").lower() else 1,
                u.get("created_at", ""),
            )
        )

    total = len(all_users)
    users = all_users[offset : offset + limit]

    # Format response
    result = []
    for u in users:
        result.append({
            "id": u.get("id"),
            "username": u.get("username"),
            "email": u.get("email"),
            "full_name": u.get("full_name"),
            "phone": u.get("phone"),
            "role": u.get("role", "user"),
            "is_active": u.get("is_active", True),
            "email_verified": u.get("email_verified", False),
            "created_at": _format_datetime(u.get("created_at")),
            "last_login_at": _format_datetime(u.get("last_login_at")),
        })

    return {
        "users": result,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    svc: AuthService = Depends(get_auth_service),
    admin: dict = Depends(require_admin),
):
    """Chi tiết một user."""
    user = svc.user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "created_at": _format_datetime(user.created_at),
        "updated_at": _format_datetime(user.updated_at),
        "last_login_at": _format_datetime(user.last_login_at),
    }


class UpdateUserRequest(BaseModel):
    """Request body để update user."""

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    svc: AuthService = Depends(get_auth_service),
    admin: dict = Depends(require_admin),
):
    """Cập nhật user."""
    # Validate role
    if req.role and req.role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")

    # Cannot change own role
    if req.role and user_id == admin["uid"]:
        raise HTTPException(status_code=400, detail="Cannot change own role")

    # Cannot deactivate self
    if req.is_active is False and user_id == admin["uid"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    try:
        updated = svc.user_repo.update_user(
            user_id=user_id,
            full_name=req.full_name,
            email=req.email,
            phone=req.phone,
            is_active=req.is_active,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")

        # Update role separately if needed
        if req.role:
            from app.core.firebase import get_firebase
            db = get_firebase().db
            db.collection("users").document(user_id).update({"role": req.role})
            updated = svc.user_repo.get_by_id(user_id)

        logger.info("Admin %s updated user %s", admin["username"], user_id)

        return {
            "id": updated.id,
            "username": updated.username,
            "email": updated.email,
            "full_name": updated.full_name,
            "phone": updated.phone,
            "role": updated.role,
            "is_active": updated.is_active,
            "email_verified": updated.email_verified,
            "created_at": _format_datetime(updated.created_at),
            "updated_at": _format_datetime(updated.updated_at),
        }
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        logger.error("Update user failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    svc: AuthService = Depends(get_auth_service),
    admin: dict = Depends(require_admin),
):
    """Xóa user (soft delete - set is_active=False)."""
    # Cannot delete self
    if user_id == admin["uid"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    # Get user first
    user = svc.user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Soft delete - just deactivate
    svc.user_repo.update_user(user_id=user_id, is_active=False)

    logger.info("Admin %s deleted/deactivated user %s", admin["username"], user_id)

    return {"message": "User deactivated successfully", "user_id": user_id}
