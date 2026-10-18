"""
==============================================================
File: deepface_service.py

DeepFaceAnalyzer - Emotion Analysis với safeguards.

Pipeline:
1. Image decode
2. Face detection (thử nhiều backends)
3. Face quality validation
4. Emotion inference
5. Reliability scoring
6. Safe burnout mapping

CRITICAL: Emotion là WEAK SIGNAL, không phải diagnosis.
==============================================================
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from app.modules.emotion.models.emotion import EmotionResult, EmotionScores
from app.modules.emotion.services.base_analyzer import (
    BaseEmotionAnalyzer,
    EmotionAnalysisError,
)
from app.modules.assessment.services.embedding_service import (
    EmbeddingUnavailableError,
)

logger = logging.getLogger("burnout.emotion")

# Confidence threshold - face phải có confidence >= 0.8 để coi là reliable
MIN_FACE_CONFIDENCE = 0.80

# Emotion reliability thresholds
EMOTION_RELIABILITY_THRESHOLDS = {
    "high": 0.85,      # raw_score >= 0.85 → high reliability
    "medium": 0.60,     # raw_score >= 0.60 → medium reliability
    "low": 0.0,        # < 0.60 → low reliability
}


class FaceDetectionResult:
    """Kết quả từ face detector."""
    def __init__(
        self,
        face_count: int = 0,
        best_confidence: float = 0.0,
        used_backend: str = "unknown",
        success: bool = False,
        error: Optional[str] = None,
    ):
        self.face_count = face_count
        self.best_confidence = best_confidence
        self.used_backend = used_backend
        self.success = success
        self.error = error


class EmotionAnalysisResult:
    """Kết quả emotion analysis với reliability."""
    def __init__(
        self,
        emotion: EmotionResult,
        face_detection: FaceDetectionResult,
        reliability_level: str = "low",
        raw_score: float = 0.0,
        warnings: list[str] | None = None,
    ):
        self.emotion = emotion
        self.face_detection = face_detection
        self.reliability_level = reliability_level
        self.raw_score = raw_score
        self.warnings = warnings or []


class DeepFaceAnalyzer(BaseEmotionAnalyzer):
    """Analyzer dùng DeepFace SDK với safeguards."""

    def __init__(self, deepface_module: Optional[Any] = None):
        """Lazy import deepface, cv2, numpy."""
        self._deepface = deepface_module
        self._cv2 = None
        self._np = None
        self._import_error: Optional[str] = None

    def _ensure_deps(self):
        """Lazy import deepface, cv2, numpy."""
        import pathlib
        import sys
        # Dynamic path discovery: find external/deepface in project tree
        _curr = pathlib.Path(__file__).resolve().parent
        while _curr != _curr.parent:
            _ext = _curr / "external"
            if (_ext / "deepface").exists():
                if str(_ext) not in sys.path:
                    sys.path.insert(0, str(_ext))
                break
            _curr = _curr.parent

        if self._deepface is None:
            try:
                from deepface import DeepFace as _DeepFace
                self._deepface = _DeepFace
                self._import_error = None
            except ImportError as exc:
                self._import_error = str(exc)
                raise EmotionAnalysisError(
                    f"DeepFace khong import duoc: {exc}"
                ) from exc
            except Exception as exc:
                self._import_error = str(exc)
                raise EmotionAnalysisError(
                    f"DeepFace import failed: {exc}"
                ) from exc

        if self._cv2 is None:
            try:
                import cv2 as _cv2
                self._cv2 = _cv2
            except ImportError as exc:
                raise EmotionAnalysisError(
                    "opencv-python (cv2) chua cai."
                ) from exc

        if self._np is None:
            try:
                import numpy as _np
                self._np = _np
            except ImportError as exc:
                raise EmotionAnalysisError(
                    "numpy chua cai."
                ) from exc

    def _get_reliability_level(self, raw_score: float) -> str:
        """Tính reliability level từ raw score."""
        if raw_score >= EMOTION_RELIABILITY_THRESHOLDS["high"]:
            return "high"
        elif raw_score >= EMOTION_RELIABILITY_THRESHOLDS["medium"]:
            return "medium"
        return "low"

    def _decode_image(self, image_bytes: bytes) -> Any:
        """Decode bytes thành numpy array và resize tối ưu nếu ảnh quá lớn."""
        np_arr = self._np.frombuffer(image_bytes, dtype=self._np.uint8)
        img_bgr = self._cv2.imdecode(np_arr, self._cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("cv2.imdecode tra None (corrupted image)")

        # Optimize: Downscale large webcam images (e.g. 1080p/2K -> max 720p) for real-time CPU inference
        if hasattr(img_bgr, "shape") and isinstance(img_bgr.shape, tuple) and len(img_bgr.shape) >= 2:
            h, w = img_bgr.shape[:2]
            max_dim = max(h, w)
            if max_dim > 720:
                scale = 720.0 / max_dim
                img_bgr = self._cv2.resize(
                    img_bgr, (int(w * scale), int(h * scale)), interpolation=self._cv2.INTER_AREA
                )
        return img_bgr

    def _extract_face_confidence(self, result: list) -> tuple[int, float]:
        """Trích xuất face count và confidence cao nhất."""
        if not result:
            return 0, 0.0

        face_count = len(result)
        best_confidence = 0.0

        for face_result in result:
            # face_confidence có thể nằm ở nhiều vị trí khác nhau tùy detector
            fc = face_result.get("face_confidence", 0.0)
            if fc is None:
                fc = 0.0
            best_confidence = max(best_confidence, fc)

        return face_count, best_confidence

    def _analyze_with_backend(self, img_bgr: Any, backend: str) -> tuple[list, str]:
        """Thử analyze với một backend cụ thể."""
        try:
            result = self._deepface.analyze(
                img_path=img_bgr,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend=backend,
            )
            return result, backend
        except Exception as exc:
            logger.warning(f"Backend {backend} failed: {exc}")
            return [], backend

    def analyze(self, image_bytes: bytes) -> EmotionResult:
        """
        Phan tich emotion với safeguards.

        Luôn tra ve EmotionResult, nhung co the la Unknown neu that bai.
        """
        # 1. Ensure dependencies
        try:
            self._ensure_deps()
        except EmotionAnalysisError as exc:
            logger.error("Dependency missing: %s", exc)
            return EmotionResult(
                emotions=EmotionScores(),
                dominant_emotion="Unknown",
                confidence=0.0,
            )

        # 2. Decode image
        try:
            img_bgr = self._decode_image(image_bytes)
        except Exception as exc:
            logger.warning("Image decode failed: %s", exc)
            return EmotionResult(
                emotions=EmotionScores(),
                dominant_emotion="Unknown",
                confidence=0.0,
            )

        # 3. Face detection - thử nhiều backends
        face_count = 0
        best_confidence = 0.0
        used_backend = "none"
        warnings = []

        # Detector priority: opencv (siêu nhanh ~0.05s) > ssd (chính xác ~0.3s) > mediapipe > mtcnn > retinaface
        detector_backends = ["opencv", "ssd", "mediapipe", "mtcnn", "retinaface"]

        for backend in detector_backends:
            result, used_backend = self._analyze_with_backend(img_bgr, backend)
            if result and len(result) > 0:
                face_count, best_confidence = self._extract_face_confidence(result)
                used_backend = backend
                logger.info(
                    f"Detector {backend}: {face_count} face(s), best_confidence={best_confidence:.3f}"
                )
                break

        # 4. Face quality validation
        if face_count == 0:
            logger.warning("No face detected")
            return EmotionResult(
                emotions=EmotionScores(),
                dominant_emotion="Unknown",
                confidence=0.0,
            )

        if face_count > 1:
            warnings.append(f"Multiple faces detected ({face_count}). Using highest confidence face.")

        if best_confidence < MIN_FACE_CONFIDENCE:
            warnings.append(
                f"Face confidence {best_confidence:.2f} < {MIN_FACE_CONFIDENCE} - low reliability"
            )

        # 5. Emotion extraction
        if not result:
            logger.warning("No emotion result from DeepFace")
            return EmotionResult(
                emotions=EmotionScores(),
                dominant_emotion="Unknown",
                confidence=0.0,
            )

        # Chon face co face_confidence cao nhat (hoac face dau tien neu khong co confidence)
        r = max(
            result,
            key=lambda f: f.get("face_confidence", 0.0) if f.get("face_confidence") is not None else 0.0,
        )
        emotions_dict = r.get("emotion", {}) or {}
        dominant = r.get("dominant_emotion", "Unknown") or "Unknown"

        # 6. Reliability calculation
        if emotions_dict:
            max_pct = max(float(v) for v in emotions_dict.values())
            raw_score = max_pct / 100.0
            confidence = round(raw_score, 4)
            reliability_level = self._get_reliability_level(raw_score)
        else:
            raw_score = 0.0
            confidence = 0.0
            reliability_level = "low"

        # 7. Build emotion scores
        try:
            scores = EmotionScores(
                happy=float(emotions_dict.get("happy", 0.0)),
                sad=float(emotions_dict.get("sad", 0.0)),
                neutral=float(emotions_dict.get("neutral", 0.0)),
                fear=float(emotions_dict.get("fear", 0.0)),
                angry=float(emotions_dict.get("angry", 0.0)),
                surprise=float(emotions_dict.get("surprise", 0.0)),
                disgust=float(emotions_dict.get("disgust", 0.0)),
            )
        except Exception:
            scores = EmotionScores()

        # 8. Age/Gender (optional, không ảnh hưởng burnout)
        age_raw = r.get("age")
        age: Optional[int] = None
        if age_raw is not None:
            try:
                age = int(age_raw)
            except (TypeError, ValueError):
                age = None

        gender_raw = r.get("dominant_gender") or r.get("gender")
        gender: Optional[str] = None
        if isinstance(gender_raw, str):
            gender = gender_raw.strip() or None

        # 9. Log warnings
        for w in warnings:
            logger.warning(w)

        # 10. Return result
        emotion_result = EmotionResult(
            emotions=scores,
            dominant_emotion=str(dominant),
            confidence=confidence,
            age=age,
            gender=gender,
        )

        # Store extra info in emotion for downstream use
        emotion_result.face_confidence = best_confidence
        emotion_result.reliability_level = reliability_level
        emotion_result.face_count = face_count
        emotion_result.detector_used = used_backend
        emotion_result.warnings = warnings

        logger.info(
            f"Emotion: {dominant} ({confidence:.2f}), "
            f"reliability={reliability_level}, "
            f"face_confidence={best_confidence:.2f}, "
            f"faces={face_count}"
        )

        return emotion_result


# ==========================================
# EmotionService (dung trong routes)
# ==========================================

class EmotionService:
    """Service dong goi: DeepFace + Repository + R2 + Assessment."""

    def __init__(
        self,
        analyzer: BaseEmotionAnalyzer,
        repository: "EmotionRepository",
        r2_service: Any,
        assessment_service: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
        qdrant_service: Optional[Any] = None,
        assessment_record_repository: Optional[Any] = None,
        **kwargs,
    ):
        self.analyzer = analyzer
        self.repository = repository
        self.r2_service = r2_service
        self.assessment_service = assessment_service
        self.embedding_service = embedding_service
        self.qdrant_service = qdrant_service
        self.assessment_record_repository = assessment_record_repository

    async def analyze(
        self,
        user_id: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
        save_image: bool = False,
        generate_ai: bool = True,
        assessment_id: Optional[str] = None,
    ) -> dict:
        """
        Pipeline:
        1. DeepFace analyze (với safeguards)
        2. Save to R2 if consent
        3. Save to Firestore
        4. AI assessment (nếu enabled)
        5. Return response
        """
        # 1. Analyze
        emotion = await asyncio.to_thread(self.analyzer.analyze, image_bytes)

        # 2. Upload R2 if consent
        image_key: Optional[str] = None
        if save_image:
            try:
                upload = await asyncio.to_thread(
                    self.r2_service.upload_image,
                    user_id,
                    image_bytes,
                    content_type,
                )
                image_key = upload.key
                emotion.image_url = image_key
            except Exception as exc:
                logger.warning("R2 upload failed: %s", exc)

        # 3. Save to Firestore
        record_id = await asyncio.to_thread(
            self.repository.save, user_id, emotion, image_key, assessment_id
        )

        # 4. AI Assessment
        assessment = None
        if generate_ai and self.assessment_service is not None:
            try:
                assessment = await self.assessment_service.generate(
                    emotion, user_id=user_id
                )
            except Exception as exc:
                logger.warning("AI generate failed: %s", exc)

            # Save assessment
            if assessment is not None:
                try:
                    snapshot = {
                        "emotions": emotion.emotions.model_dump(),
                        "dominant_emotion": emotion.dominant_emotion,
                        "confidence": emotion.confidence,
                        "reliability_level": getattr(emotion, "reliability_level", "unknown"),
                        "face_confidence": getattr(emotion, "face_confidence", 0.0),
                        "face_count": getattr(emotion, "face_count", 0),
                        "warnings": getattr(emotion, "warnings", []),
                    }
                    if getattr(self, "assessment_record_repository", None) is not None:
                        await asyncio.to_thread(
                            self.assessment_record_repository.save,
                            emotion_id=record_id,
                            user_id=user_id,
                            risk_level=assessment.risk_level,
                            summary=assessment.summary,
                            recommendations=assessment.recommendations,
                            key_signals=assessment.key_signals,
                            disclaimer=assessment.disclaimer,
                            ai_model=assessment.ai_model or "unknown",
                            ai_prompt_version=assessment.ai_prompt_version or "v1.0",
                            input_emotion_snapshot=snapshot,
                        )
                    else:
                        await asyncio.to_thread(
                            self.repository.update_assessment,
                            emotion_id=record_id,
                            risk_level=assessment.risk_level,
                            summary=assessment.summary,
                            recommendations=assessment.recommendations,
                            key_signals=assessment.key_signals,
                            disclaimer=assessment.disclaimer,
                            ai_model=assessment.ai_model or "unknown",
                            ai_prompt_version=assessment.ai_prompt_version or "v1.0",
                            input_emotion_snapshot=snapshot,
                        )
                except Exception as exc:
                    logger.warning("Save assessment failed: %s", exc)

        # 5. Generate presigned URL
        image_url: Optional[str] = None
        if image_key:
            try:
                image_url = await asyncio.to_thread(
                    self.r2_service.generate_presigned_url, image_key
                )
            except Exception as exc:
                logger.warning("generate_presigned_url failed: %s", exc)

        # 6. Return response
        emotion_for_response = emotion.model_dump()
        emotion_for_response.pop("image_url", None)

        return {
            "request_id": record_id,
            "emotion": emotion_for_response,
            "assessment": (
                assessment.model_dump() if assessment is not None else None
            ),
            "image_key": image_key,
            "image_url": image_url,
            "saved_to_r2": bool(image_key),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }


# ==========================================
# Singleton
# ==========================================

_emotion_service: Optional[EmotionService] = None


def get_emotion_service() -> EmotionService:
    """Lay EmotionService singleton."""
    global _emotion_service
    if _emotion_service is None:
        from app.modules.assessment.services.ai_service import get_assessment_service
        from app.modules.assessment.services.embedding_service import (
            get_embedding_service,
        )
        from app.modules.assessment.services.qdrant_service import (
            get_qdrant_service,
        )
        from app.modules.emotion.repositories.emotion_repository import (
            EmotionRepository,
        )
        from app.modules.storage import get_r2_service

        _emotion_service = EmotionService(
            analyzer=DeepFaceAnalyzer(),
            repository=EmotionRepository(),
            r2_service=get_r2_service(),
            assessment_service=get_assessment_service(),
            embedding_service=get_embedding_service(),
            qdrant_service=get_qdrant_service(),
        )
    return _emotion_service
