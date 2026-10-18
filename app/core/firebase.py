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

import json
import logging
import os
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials, firestore

logger = logging.getLogger("firebase.core")


def find_firebase_credential_path(custom_path: Optional[str] = None) -> Optional[str]:
    """
    Tự động dò tìm file service account key ở mọi vị trí có thể có:
    - Custom path / GOOGLE_APPLICATION_CREDENTIALS
    - /etc/secrets/ (Render Secret Files mount)
    - App root (/app/serviceAccountKey.json hoặc ./serviceAccountKey.json)
    - config/serviceAccountKey.json
    """
    root_path = Path(__file__).resolve().parent.parent.parent
    env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    candidates = [
        custom_path,
        env_path,
        "/etc/secrets/serviceAccountKey.json",
        "/etc/secrets/config/serviceAccountKey.json",
        str(root_path / "serviceAccountKey.json"),
        str(root_path / "config" / "serviceAccountKey.json"),
        "serviceAccountKey.json",
        "config/serviceAccountKey.json",
        "/app/serviceAccountKey.json",
        "/app/config/serviceAccountKey.json",
    ]

    for c in candidates:
        if c and not c.strip().startswith("{"):
            p = Path(c)
            if not p.is_absolute():
                p_cand = root_path / p
                if p_cand.exists() and (p_cand.is_file() or p_cand.is_symlink()):
                    logger.info("Found Firebase credential at: %s", p_cand.resolve())
                    return str(p_cand.resolve())
            if p.exists() and (p.is_file() or p.is_symlink()):
                logger.info("Found Firebase credential at: %s", p.resolve())
                return str(p.resolve())

    # Quét thư mục /etc/secrets (Render secret files)
    sec_dir = Path("/etc/secrets")
    if sec_dir.exists():
        try:
            for jf in sec_dir.glob("*.json"):
                if jf.is_file() or jf.is_symlink():
                    logger.info("Found Firebase credential in /etc/secrets: %s", jf.resolve())
                    return str(jf.resolve())
        except Exception as e:
            logger.warning("Error reading /etc/secrets: %s", e)

    # Quét thư mục root
    try:
        for jf in root_path.glob("*.json"):
            if (jf.is_file() or jf.is_symlink()) and ("serviceAccount" in jf.name or "firebase" in jf.name):
                logger.info("Found Firebase credential in app root: %s", jf.resolve())
                return str(jf.resolve())
    except Exception as e:
        logger.warning("Error reading root path: %s", e)

    return None


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

        Hỗ trợ:
        1. JSON string trực tiếp qua env `FIREBASE_SERVICE_ACCOUNT_JSON` hoặc `FIREBASE_CREDENTIALS_JSON`.
        2. JSON string hoặc file path trong `GOOGLE_APPLICATION_CREDENTIALS` / `credential_path`.
        3. Application Default Credentials (ADC) khi chạy trên GCP / Cloud Run.

        Args:
            credential_path: Đường dẫn đến file JSON hoặc JSON string.
            project_id: Firebase project ID (tuỳ chọn).
        """
        if self._app is not None:
            return  # Đã initialize rồi

        cred = None

        # 1. Thử lấy raw JSON string từ environment variables (rất phổ biến khi deploy Docker/Cloud)
        raw_json = (
            os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            or os.getenv("FIREBASE_CREDENTIALS_JSON")
        )

        if not raw_json and credential_path and credential_path.strip().startswith("{"):
            raw_json = credential_path

        env_cred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not raw_json and env_cred and env_cred.strip().startswith("{"):
            raw_json = env_cred

        if raw_json:
            try:
                cert_dict = json.loads(raw_json.strip())
                cred = credentials.Certificate(cert_dict)
                logger.info("Firebase initialized using raw JSON credentials.")
            except Exception as e:
                logger.error(f"Failed to parse Firebase raw JSON credentials: {e}")

        # 2. Nếu không có raw JSON, kiểm tra file path
        if cred is None:
            found_file = find_firebase_credential_path(credential_path)
            if found_file:
                cred = credentials.Certificate(found_file)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = found_file
                logger.info(f"Firebase initialized from certificate file: {found_file}")

        # 3. Khởi tạo App
        if cred is not None:
            self._app = firebase_admin.initialize_app(
                cred,
                options={"projectId": project_id} if project_id else None
            )
        else:
            # Thử dùng Application Default Credentials (ADC)
            # Phù hợp cho Cloud Run, GCE, local dev với gcloud auth
            logger.info("Initializing Firebase using Application Default Credentials (ADC).")
            # Xoá env var nếu trỏ vào file không tồn tại để ADC không crash
            if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
                if not Path(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]).exists():
                    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
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
                # Kiểm tra nếu có raw JSON env var
                if (
                    os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
                    or os.getenv("FIREBASE_CREDENTIALS_JSON")
                ):
                    self.initialize()
                else:
                    found_path = find_firebase_credential_path()
                    self.initialize(credential_path=found_path)
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
