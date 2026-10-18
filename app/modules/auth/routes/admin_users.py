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
    """Chi tiết đầy đủ một user (cho Admin)."""
    from app.core.firebase import get_firebase
    db = get_firebase().db
    doc = db.collection("users").document(user_id).get()
    
    if not doc.exists:
        # Fallback to user_repo lookup
        user = svc.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
            "is_active": user.is_active,
            "email_verified": user.email_verified,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login_at": user.last_login_at,
        }
    else:
        data = doc.to_dict() or {}
        data["id"] = doc.id

    avatar_val = data.get("avatar") or data.get("avatar_url") or ""

    return {
        "id": data.get("id", user_id),
        "uid": data.get("id", user_id),
        "username": data.get("username", ""),
        "email": data.get("email", ""),
        "full_name": data.get("full_name") or data.get("username", ""),
        "phone": data.get("phone", ""),
        "avatar": avatar_val,
        "avatar_url": avatar_val,
        "role": data.get("role", "user"),
        "is_active": data.get("is_active", True),
        "email_verified": data.get("email_verified", False),
        "gender": data.get("gender"),
        "birthday": data.get("birthday"),
        "job_title": data.get("job_title"),
        "standard_working_hours_per_day": data.get("standard_working_hours_per_day", 8.0),
        "work_days_per_week": data.get("work_days_per_week", 5),
        "average_overtime_hours_per_week": data.get("average_overtime_hours_per_week", 0.0),
        "created_at": _format_datetime(data.get("created_at")),
        "updated_at": _format_datetime(data.get("updated_at")),
        "last_login_at": _format_datetime(data.get("last_login_at")),
    }


class UpdateUserRequest(BaseModel):
    """Request body để update user."""

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    gender: Optional[str] = None
    birthday: Optional[str] = None
    job_title: Optional[str] = None
    standard_working_hours_per_day: Optional[float] = None
    work_days_per_week: Optional[int] = None
    average_overtime_hours_per_week: Optional[float] = None


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
        from app.core.firebase import get_firebase
        from datetime import datetime
        db = get_firebase().db
        
        # Build update dict
        update_dict = {"updated_at": datetime.utcnow()}
        if req.full_name is not None:
            update_dict["full_name"] = req.full_name
        if req.email is not None:
            update_dict["email"] = req.email.strip().lower()
        if req.phone is not None:
            update_dict["phone"] = req.phone
        if req.is_active is not None:
            update_dict["is_active"] = req.is_active
            try:
                from firebase_admin import auth as fb_auth
                fb_auth.update_user(user_id, disabled=not req.is_active)
                logger.info("Firebase Auth user %s disabled=%s", user_id, not req.is_active)
            except Exception as e:
                logger.warning("Could not sync disabled status with Firebase Auth for %s: %s", user_id, e)

        if req.role is not None:
            update_dict["role"] = req.role
        if req.gender is not None:
            update_dict["gender"] = req.gender
        if req.birthday is not None:
            update_dict["birthday"] = req.birthday
        if req.job_title is not None:
            update_dict["job_title"] = req.job_title
        if req.standard_working_hours_per_day is not None:
            update_dict["standard_working_hours_per_day"] = float(req.standard_working_hours_per_day)
        if req.work_days_per_week is not None:
            update_dict["work_days_per_week"] = int(req.work_days_per_week)
        if req.average_overtime_hours_per_week is not None:
            update_dict["average_overtime_hours_per_week"] = float(req.average_overtime_hours_per_week)

        db.collection("users").document(user_id).set(update_dict, merge=True)
        logger.info("Admin %s updated user %s with %s", admin.get("username", "admin"), user_id, list(update_dict.keys()))

        # Return updated user
        doc = db.collection("users").document(user_id).get()
        data = doc.to_dict() or {}
        avatar_val = data.get("avatar") or data.get("avatar_url") or ""

        return {
            "id": user_id,
            "uid": user_id,
            "username": data.get("username", ""),
            "email": data.get("email", ""),
            "full_name": data.get("full_name") or data.get("username", ""),
            "phone": data.get("phone", ""),
            "avatar": avatar_val,
            "avatar_url": avatar_val,
            "role": data.get("role", "user"),
            "is_active": data.get("is_active", True),
            "email_verified": data.get("email_verified", False),
            "gender": data.get("gender"),
            "birthday": data.get("birthday"),
            "job_title": data.get("job_title"),
            "standard_working_hours_per_day": data.get("standard_working_hours_per_day", 8.0),
            "work_days_per_week": data.get("work_days_per_week", 5),
            "average_overtime_hours_per_week": data.get("average_overtime_hours_per_week", 0.0),
            "created_at": _format_datetime(data.get("created_at")),
            "updated_at": _format_datetime(data.get("updated_at")),
            "last_login_at": _format_datetime(data.get("last_login_at")),
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
    """Vô hiệu hóa user (soft delete - set is_active=False, bảo lưu toàn bộ dữ liệu lịch sử)."""
    # Cannot delete self
    if user_id == admin["uid"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    from app.core.firebase import get_firebase
    from datetime import datetime
    db = get_firebase().db
    doc_ref = db.collection("users").document(user_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    # Soft delete: update is_active to False in Firestore (dữ liệu không bao giờ bị xóa vĩnh viễn)
    doc_ref.set({
        "is_active": False,
        "updated_at": datetime.utcnow()
    }, merge=True)

    # Disable in Firebase Auth
    try:
        from firebase_admin import auth as fb_auth
        fb_auth.update_user(user_id, disabled=True)
        logger.info("Firebase Auth user %s disabled=True", user_id)
    except Exception as e:
        logger.warning("Could not disable user in Firebase Auth for %s: %s", user_id, e)

    logger.info("Admin %s deactivated user %s", admin.get("username", "admin"), user_id)

    return {"message": "User deactivated successfully", "user_id": user_id, "is_active": False}
