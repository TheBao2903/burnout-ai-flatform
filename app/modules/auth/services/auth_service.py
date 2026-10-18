"""
==============================================================
File: auth_service.py

AuthService - signup, admin_create_user, login, JWT verify.

Password: bcrypt (12 rounds).
Token: JWT HS256 (24h mac dinh).
==============================================================
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import bcrypt
except ImportError:
    bcrypt = None  # Fallback if running outside venv or bcrypt not installed
import jwt
from pydantic import EmailStr

from app.core.settings import get_settings
from app.modules.auth.models.user import (
    LoginResponse,
    User,
    UserPublic,
)
from app.modules.auth.repositories.user_repository import UserRepository

logger = logging.getLogger("burnout.auth.service")


class AuthError(Exception):
    """Loi auth (sai user/pass, token sai, ...)."""

    def __init__(self, message: str, code: str = "auth_error", wait_seconds: int = 0):
        super().__init__(message)
        self.message = message
        self.code = code
        self.wait_seconds = wait_seconds


class AuthService:
    """Service xu ly signup, login, verify token."""

    # Configurable refresh token expiry (days)
    REFRESH_TOKEN_EXPIRE_DAYS = 7

    def __init__(self, user_repo: Optional[UserRepository] = None):
        self.user_repo = user_repo or UserRepository()
        self._refresh_token_repo = None

    @property
    def refresh_token_repo(self):
        """Lazy init refresh token repo."""
        if self._refresh_token_repo is None:
            from app.modules.auth.repositories.refresh_token_repository import (
                RefreshTokenRepository,
            )
            self._refresh_token_repo = RefreshTokenRepository(
                expire_days=self.REFRESH_TOKEN_EXPIRE_DAYS
            )
        return self._refresh_token_repo

    # -------------------------
    # Password
    # -------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password bang bcrypt."""
        if bcrypt is None:
            raise RuntimeError("bcrypt module is not installed. Please activate venv or install bcrypt.")
        salt = bcrypt.gensalt(rounds=get_settings().auth.bcrypt_rounds)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        if bcrypt is None:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            return False

    # -------------------------
    # JWT
    # -------------------------

    def create_access_token(self, user: User) -> tuple[str, int]:
        settings = get_settings().auth
        expire_hours = settings.jwt_expire_hours
        expire_at = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "iat": datetime.now(timezone.utc),
            "exp": expire_at,
        }
        token = jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
        return token, expire_hours

    def create_refresh_token(self, user_id: str) -> tuple[str, int]:
        """Tạo refresh token mới cho user.

        Args:
            user_id: User ID.

        Returns:
            (refresh_token, expires_in_days).
        """
        token, expires_at = self.refresh_token_repo.create(user_id)
        expires_in_days = (expires_at - datetime.utcnow()).days
        return token, expires_in_days

    def verify_token(self, token: str) -> dict:
        settings = get_settings().auth
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired")
        except jwt.InvalidTokenError as exc:
            raise AuthError(f"Invalid token: {exc}")
        return payload

    def refresh_access_token(self, refresh_token: str) -> tuple[str, str, int, int]:
        """Refresh access token bằng refresh token.

        Token cũ bị revoke, tạo token mới.

        Args:
            refresh_token: Refresh token.

        Returns:
            (access_token, new_refresh_token, expires_in_hours, refresh_expires_in_days).

        Raises:
            AuthError nếu refresh token không hợp lệ.
        """
        user_id = self.refresh_token_repo.verify(refresh_token)
        if not user_id:
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn")

        # Get user
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise AuthError("User không tồn tại")

        # Rotate token (revoke old, create new)
        result = self.refresh_token_repo.rotate(refresh_token)
        if not result:
            raise AuthError("Không thể refresh token")

        new_refresh_token, refresh_expires_at = result
        refresh_expires_in_days = (refresh_expires_at - datetime.utcnow()).days

        # Create new access token
        access_token, expires_in_hours = self.create_access_token(user)

        logger.info("Token refreshed for user %s", user.username)
        return access_token, new_refresh_token, expires_in_hours, refresh_expires_in_days

    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke refresh token (logout).

        Args:
            refresh_token: Refresh token cần revoke.

        Returns:
            True nếu thành công.
        """
        return self.refresh_token_repo.revoke(refresh_token)

    def revoke_all_refresh_tokens(self, user_id: str) -> int:
        """Revoke tất cả refresh tokens của user.

        Args:
            user_id: User ID.

        Returns:
            Số tokens đã revoke.
        """
        return self.refresh_token_repo.revoke_all_for_user(user_id)

    # -------------------------
    # Validation
    # -------------------------

    @staticmethod
    def _validate_username(username: str) -> str:
        settings = get_settings().auth
        username = username.strip().lower()
        if len(username) < settings.min_username_length:
            raise AuthError(f"Username qua ngan (min {settings.min_username_length})")
        if not username.replace("_", "").replace("-", "").isalnum():
            raise AuthError("Username chi chua chu, so, _, -")
        return username

    @staticmethod
    def _validate_password(password: str) -> str:
        settings = get_settings().auth
        if len(password) < settings.min_password_length:
            raise AuthError(f"Password qua ngan (min {settings.min_password_length})")
        return password

    @staticmethod
    def _validate_full_name(full_name: str) -> str:
        full_name = full_name.strip()
        if not full_name:
            raise AuthError("Full name khong duoc rong")
        return full_name

    # -------------------------
    # Self signup (email REQUIRED)
    # -------------------------

    def signup(
        self,
        username: str,
        password: str,
        email: str,
        full_name: Optional[str] = None,
    ) -> LoginResponse:
        """User tu dang ky. Email la BAT BUOC."""
        username = self._validate_username(username)
        password = self._validate_password(password)
        email = email.strip().lower()
        # Pydantic da validate email format (EmailStr), nhung check them:
        if not email or "@" not in email:
            raise AuthError("Email la bat buoc khi tu dang ky")

        password_hash = self.hash_password(password)
        try:
            user = self.user_repo.create(
                username=username,
                password_hash=password_hash,
                email=email,
                full_name=full_name,
                role="user",
                is_active=True,
                email_verified=False,
            )
        except ValueError as exc:
            raise AuthError(str(exc))

        token, expire_hours = self.create_access_token(user)
        refresh_token, refresh_expires_days = self.create_refresh_token(user.id)
        logger.info("Self signup: %s (email=%s)", username, email)
        return self._to_login_response(user, token, expire_hours, refresh_token, refresh_expires_days)

    # -------------------------
    # Admin create-user (full_name REQUIRED, email/phone optional)
    # -------------------------

    def admin_create_user(
        self,
        username: str,
        password: str,
        full_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "user",
    ) -> UserPublic:
        """Admin tao user moi. Email/phone optional, full_name bat buoc."""
        username = self._validate_username(username)
        password = self._validate_password(password)
        full_name = self._validate_full_name(full_name)

        if email:
            email = email.strip().lower()
        if phone:
            phone = phone.strip()

        password_hash = self.hash_password(password)
        try:
            user = self.user_repo.create(
                username=username,
                password_hash=password_hash,
                email=email,
                full_name=full_name,
                phone=phone,
                role=role,
                is_active=True,
                # Admin tao thi tu tin tuong, set verified=true neu co email
                email_verified=bool(email),
            )
        except ValueError as exc:
            raise AuthError(str(exc))

        logger.info("Admin created user: %s (full_name=%s, role=%s)", username, full_name, role)
        return self._to_public(user)

    # -------------------------
    # Login
    # -------------------------

    def login(self, username: str, password: str) -> LoginResponse:
        from app.modules.auth.services.login_rate_limiter import get_login_rate_limiter

        username = username.strip().lower()
        limiter = get_login_rate_limiter()

        # Check if locked
        if limiter.is_locked(username):
            wait_seconds = limiter.get_wait_seconds(username)
            raise AuthError(
                f"Tai khoan tam thoi bi khoa. Vui long cho {wait_seconds} giay.",
                code="account_locked",
                wait_seconds=wait_seconds,
            )

        # Attempt login
        user = self.user_repo.get_by_username(username)
        if user is None:
            # Log failed login attempt (user not found)
            self._log_login_activity(None, success=False)
            failure = limiter.record_failure(username)
            if failure["locked"]:
                raise AuthError(
                    f"Tai khoan tam thoi bi khoa. Vui long cho {failure['wait_seconds']} giay.",
                    code="account_locked",
                    wait_seconds=failure["wait_seconds"],
                )
            raise AuthError("Username hoac password sai")

        if not user.is_active:
            raise AuthError("Tai khoan da bi khoa")

        if not self.verify_password(password, user.password_hash):
            # Log failed login attempt (wrong password)
            self._log_login_activity(user.id, success=False)
            failure = limiter.record_failure(username)
            if failure["locked"]:
                raise AuthError(
                    f"Tai khoan tam thoi bi khoa. Vui long cho {failure['wait_seconds']} giay.",
                    code="account_locked",
                    wait_seconds=failure["wait_seconds"],
                )
            raise AuthError("Username hoac password sai")

        # Login successful - reset attempts
        limiter.record_success(username)

        self.user_repo.update_last_login(user.id)
        user.last_login_at = datetime.utcnow()

        # Log login activity for analytics
        self._log_login_activity(user.id, success=True)

        token, expire_hours = self.create_access_token(user)
        refresh_token, refresh_expires_days = self.create_refresh_token(user.id)
        logger.info("Login success: %s (role=%s)", username, user.role)
        return self._to_login_response(user, token, expire_hours, refresh_token, refresh_expires_days)

    def get_current_user(self, token: str) -> User:
        payload = self.verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("Token thieu 'sub'")
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise AuthError("User khong ton tai")
        return user

    def get_current_user_by_id(self, user_id: str) -> User:
        """Lay user theo id (KHONG qua token)."""
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise AuthError("User khong ton tai")
        return user

    # -------------------------
    # Bootstrap admin (FIRST admin only)
    # -------------------------

    def has_any_admin(self) -> bool:
        """Kiem tra DB da co admin nao chua."""
        # Query users co role=admin
        from google.cloud import firestore  # noqa
        admin_docs = self.user_repo.collection.where("role", "==", "admin").limit(1).stream()
        return any(admin_docs)

    def bootstrap_first_admin(
        self,
        username: str,
        password: str,
        full_name: str,
        email: str,
    ) -> LoginResponse:
        """Tao admin DAU TIEN trong he thong.

        Chi thanh cong neu DB chua co admin nao. Sau khi co 1 admin,
        cac admin moi phai duoc tao qua /admin/create-user (can admin token).
        """
        if self.has_any_admin():
            raise AuthError("Admin da ton tai trong he thong. Dung /admin/create-user de tao them.")

        username = self._validate_username(username)
        password = self._validate_password(password)
        full_name = self._validate_full_name(full_name)
        email = email.strip().lower()
        if not email or "@" not in email:
            raise AuthError("Email la bat buoc cho first admin")

        password_hash = self.hash_password(password)
        try:
            user = self.user_repo.create(
                username=username,
                password_hash=password_hash,
                email=email,
                full_name=full_name,
                role="admin",  # FIRST ADMIN
                is_active=True,
                email_verified=True,
            )
        except ValueError as exc:
            raise AuthError(str(exc))

        token, expire_hours = self.create_access_token(user)
        refresh_token, refresh_expires_days = self.create_refresh_token(user.id)
        logger.info("Bootstrap first admin: %s (email=%s)", username, email)
        return self._to_login_response(user, token, expire_hours, refresh_token, refresh_expires_days)

    # -------------------------
    # Helpers
    # -------------------------

    @staticmethod
    def _to_public(user: User) -> UserPublic:
        return UserPublic(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            avatar_url=user.avatar_url,
            role=user.role,
            is_active=user.is_active,
            email_verified=user.email_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
        )

    # -------------------------
    # Update profile
    # -------------------------

    def update_profile(
        self,
        user_id: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> UserPublic:
        """User tu update profile cua minh.

        Args:
            user_id: Tu JWT token.
            full_name, email, phone, avatar_url: Chi update field truyen vao (None = giu nguyen).

        Raises:
            AuthError neu email trung voi user khac.
        """
        if email is not None:
            email = email.strip().lower()
            if email and "@" not in email:
                raise AuthError("Email khong hop le")
            existing = self.user_repo.get_by_email(email)
            if existing and existing.id != user_id:
                raise AuthError("Email da duoc su dung boi user khac")

        user = self.user_repo.update_user(
            user_id=user_id,
            full_name=full_name,
            email=email,
            phone=phone,
            avatar_url=avatar_url,
        )
        if user is None:
            raise AuthError("User khong ton tai")
        logger.info("Profile updated: %s (id=%s)", user.username, user.id)
        return self._to_public(user)

    @staticmethod
    def _to_login_response(
        user: User,
        token: str,
        expire_hours: int,
        refresh_token: Optional[str] = None,
        refresh_expires_days: Optional[int] = None,
    ) -> LoginResponse:
        return LoginResponse(
            access_token=token,
            expires_in_hours=expire_hours,
            refresh_token=refresh_token or "",
            refresh_expires_in_days=refresh_expires_days or 0,
            user=AuthService._to_public(user),
        )

    def _log_login_activity(self, user_id: str, success: bool, ip_address: str = None, user_agent: str = None) -> None:
        """Log login activity to Firestore for analytics.

        Args:
            user_id: User ID
            success: True if login successful
            ip_address: Client IP address
            user_agent: Client user agent
        """
        try:
            from app.core.firebase import get_firebase, FirestoreCollections
            db = get_firebase().db
            now = datetime.utcnow()

            login_activity = {
                "user_id": user_id,
                "timestamp": now,
                "success": success,
                "ip_address": ip_address or "unknown",
                "user_agent": user_agent or "unknown",
            }

            db.collection(FirestoreCollections.LOGIN_ACTIVITIES).document().set(login_activity)
            logger.debug("Logged login activity for user %s (success=%s)", user_id, success)
        except Exception as e:
            # Don't fail login if logging fails
            logger.warning("Failed to log login activity: %s", e)


# ==========================================
# Singleton
# ==========================================

_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service