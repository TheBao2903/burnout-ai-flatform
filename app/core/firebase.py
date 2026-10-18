"""
==============================================================
File: firebase.py

Chức năng:
- Cấu hình và khởi tạo Firebase Admin SDK.
- Kết nối Firestore cho backend.

Cách sử dụng:
1. Download service account key từ Firebase Console
2. Đặt file JSON vào thư mục config/
3. Set GOOGLE_APPLICATION_CREDENTIALS trong .env

Được sử dụng tại:
- Database Repository
- Auth Service (Firestore)
- API Endpoints
==============================================================
"""

import os
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials, firestore


class FirebaseConfig:
    """
    Singleton class quản lý Firebase connection.
    """

    _instance: Optional["FirebaseConfig"] = None
    _app: Optional[firebase_admin.App] = None
    _db: Optional[firestore.Client] = None

    def __new__(cls) -> "FirebaseConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._app is not None:
            return  # Đã được khởi tạo

    def initialize(
        self,
        credential_path: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> None:
        """
        Khởi tạo Firebase Admin SDK.

        Args:
            credential_path: Đường dẫn đến service account JSON file.
                           Nếu None, sẽ dùng GOOGLE_APPLICATION_CREDENTIALS env var.
            project_id: Firebase project ID. Nếu None, dùng từ credentials.
        """
        if self._app is not None:
            return  # Đã initialize rồi

        # Tìm credentials
        if credential_path is None:
            credential_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if credential_path:
            # Sử dụng service account file
            cred = credentials.Certificate(credential_path)
            self._app = firebase_admin.initialize_app(
                cred,
                options={"projectId": project_id} if project_id else None
            )
        else:
            # Thử dùng Application Default Credentials (ADC)
            # Phù hợp cho Cloud Run, GCE, local dev với gcloud auth
            self._app = firebase_admin.initialize_app()

        # Initialize Firestore client
        self._db = firestore.client()

    @property
    def db(self) -> firestore.Client:
        """
        Lấy Firestore client. Tự động lazy initialize nếu chưa khởi tạo.
        """
        if self._db is None:
            try:
                root_path = Path(__file__).resolve().parent.parent.parent
                cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or str(root_path / "config" / "serviceAccountKey.json")
                if not Path(cred_path).is_absolute():
                    cred_path = str(root_path / cred_path)
                self.initialize(credential_path=cred_path if Path(cred_path).exists() else None)
            except Exception as e:
                raise RuntimeError(
                    f"Firebase chưa được khởi tạo và lazy init thất bại: {e}"
                ) from e
        return self._db

    @property
    def app(self) -> firebase_admin.App:
        """Lấy Firebase app instance."""
        if self._app is None:
            _ = self.db  # Kích hoạt lazy init nếu chưa khởi tạo
        return self._app

    def close(self) -> None:
        """Đóng Firebase connection."""
        if self._app is not None:
            firebase_admin.delete_app(self._app)
            self._app = None
            self._db = None


# ==========================================
# GLOBAL INSTANCE
# ==========================================

def get_firebase() -> FirebaseConfig:
    """Lấy global FirebaseConfig instance."""
    return FirebaseConfig()


def init_firebase(
    credential_path: Optional[str] = None,
    project_id: Optional[str] = None
) -> firestore.Client:
    """
    Helper function để khởi tạo Firebase nhanh.

    Usage:
        db = init_firebase("path/to/serviceAccountKey.json")
        # hoặc
        db = init_firebase(project_id="my-project")
    """
    config = get_firebase()
    config.initialize(credential_path=credential_path, project_id=project_id)
    return config.db


# ==========================================
# COLLECTION REFERENCES
# ==========================================

class FirestoreCollections:
    """
    Constants cho các collection names.
    """

    USERS = "users"
    SESSIONS = "sessions"
    EMOTIONS = "emotions"
    ASSESSMENTS = "assessments"
    BURNOUT_RESULTS = "burnout_results"
    RECOMMENDATIONS = "recommendations"
    CHATS = "chats"
    REPORTS = "reports"
    NOTIFICATIONS = "notifications"
    TIMELINES = "timelines"

    # History collections (lưu lịch sử user)
    CHAT_HISTORY = "chat_history"      # Lịch sử chat messages
    SURVEY_HISTORY = "survey_history"  # Lịch sử survey responses
    PERIODIC_SURVEYS = "periodic_surveys"  # Khảo sát định kỳ (Job Resources + Six Areas)

    # Auth-related collections
    AUTH_SESSIONS = "auth_sessions"
    PASSWORD_RESET_TOKENS = "password_reset_tokens"
    LOGIN_ACTIVITIES = "login_activities"
    SECURITY_EVENTS = "security_events"

    # Recommendation collections
    RECOMMENDATION_HISTORY = "recommendation_history"
    RECOMMENDATION_INTERACTIONS = "recommendation_interactions"
    USER_RECOMMENDATION_PROFILES = "user_recommendation_profiles"
    PLACE_INTERACTIONS = "place_interactions"


def get_collection(collection_name: str):
    """
    Lấy reference đến một collection.

    Usage:
        users_ref = get_collection("users")
        doc_ref = users_ref.document("user_123")
    """
    return get_firebase().db.collection(collection_name)


# ==========================================
# FIREBASE AUTH HELPERS
# ==========================================

def verify_firebase_token(id_token: str) -> dict:
    """
    Verify Firebase ID token (JWT do Firebase client SDK cấp).

    Args:
        id_token: Token nhận được từ client sau khi signIn/signUp.

    Returns:
        Dict các claims: uid, email, name, picture, email_verified, ...

    Raises:
        fb_auth.ExpiredIdTokenError: Token hết hạn.
        fb_auth.InvalidIdTokenError: Token sai.
    """
    return fb_auth.verify_id_token(id_token)


def get_user_by_uid(uid: str) -> dict:
    """
    Lấy thông tin user từ Firebase Auth bằng UID.

    Returns:
        Dict {uid, email, display_name, photo_url, email_verified}.
    """
    rec = fb_auth.get_user(uid)
    return {
        "uid": rec.uid,
        "email": rec.email,
        "display_name": rec.display_name,
        "photo_url": rec.photo_url,
        "email_verified": rec.email_verified,
    }
