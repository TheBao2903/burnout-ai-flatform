"""
==============================================================
File: ai_service.py

AssessmentService - Sinh danh gia nguy co Burnout tu EmotionResult
su dung Google AI Studio (Gemini API).

Input chi la JSON emotion (khong nhan anh).
Output co cau truc: risk_level, summary, recommendations,
key_signals, disclaimer.

Fallback: neu Gemini loi hoac key rong -> tra medium + disclaimer.
==============================================================
"""

import asyncio
import json
import logging
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.settings import get_settings
from app.modules.emotion.models.emotion import EmotionResult

logger = logging.getLogger("burnout.assessment")

# Sprint 19: RAG context config
RAG_TOP_K = 5  # So snapshot similar nhat de inject vao prompt (case memory)
# Sprint 21: Knowledge RAG
KNOWLEDGE_TOP_K = 3  # So knowledge docs gan emotion nhat de inject


# ==========================================
# Schema
# ==========================================

DEFAULT_DISCLAIMER = (
    "AI chỉ đánh giá nguy cơ, không chẩn đoán bệnh. "
    "Nếu kéo dài, hãy gặp chuyên gia."
)

# Version cua system prompt - bump khi thay doi de biet assessment cu su dung prompt nao
AI_PROMPT_VERSION = "v2.0"


class AIAssessmentResult(BaseModel):
    """Ket qua AI assessment."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "risk_level": "medium",
                "summary": "Cảm xúc tiêu cực nhẹ, cần chú ý nghỉ ngơi.",
                "recommendations": [
                    "Nghỉ ngơi",
                    "Ngủ đủ giấc (7-8 tiếng)",
                    "Trao đổi với quản lý",
                ],
                "key_signals": ["sad dominant", "confidence 0.6"],
                "disclaimer": DEFAULT_DISCLAIMER,
            }
        }
    )

    risk_level: Literal["low", "medium", "high", "can_theo_doi"]
    summary: str = Field(..., min_length=1, max_length=1000)
    recommendations: List[str] = Field(..., min_length=1)
    key_signals: List[str] = Field(default_factory=list)
    disclaimer: str = Field(default=DEFAULT_DISCLAIMER)
    ai_model: Optional[str] = Field(default=None, description="Model AI da generate (vd gemini-3.5-flash)")
    ai_prompt_version: Optional[str] = Field(default=None, description="Version system prompt")


# ==========================================
# Fallback
# ==========================================

def _fallback_assessment(message: str = "Khong the phan tich chi tiet.") -> AIAssessmentResult:
    """Fallback assessment khi Gemini loi hoac key rong."""
    return AIAssessmentResult(
        risk_level="medium",
        summary=message + " Vui lòng thử lại sau.",
        recommendations=["Nghỉ ngơi", "Thử lại sau", "Liên hệ hỗ trợ"],
        key_signals=[],
        disclaimer=DEFAULT_DISCLAIMER,
        ai_model=None,  # fallback: khong co model that su dung
        ai_prompt_version=AI_PROMPT_VERSION,
    )


# ==========================================
# Service
# ==========================================

SYSTEM_PROMPT = (
    "Ban la AI ho tro sang loc som nguy co Burnout. Ban KHONG chan doan benh tam than.\n"
    "Ban chi danh gia muc do nguy co dua tren tin hieu cam xuc va dua khuyen nghi.\n"
    "\n"
    "QUAN TRONG - VE DO TIN CAY:\n"
    "- Diem confidence cua emotion model la RAW SCORE, khong phai do chinh xac cham xuc that\n"
    "- Mot hinh anh don le KHONG DU de chan doan burnout\n"
    "- Neu chi co 1 hinh anh: tra risk_level = 'can_theo_doi' + giai thich\n"
    "- TIN HIEU CAM XUC TU HINH ANH CHI LA MOT YEU TO HO TRO, khong phai ket luan\n"
    "\n"
    "Dieu kien tra ve LOW/MEDIUM/HIGH:\n"
    "- Chi duoc tra 'low'/'medium'/'high' khi co nhieu du lieu (nhieu hinh anh, xu huong dai han)\n"
    "- Neu chi co 1 hinh anh: tra 'can_theo_doi' + giai thich can theo doi them\n"
    "- Tuyet doi KHONG map truc tiep emotion sang burnout level\n"
    "\n"
    "Luon tra loi bang tieng Viet, bang JSON HOP LE (KHONG chen text ngoai JSON), theo schema: "
    '{"risk_level":"low|medium|high|can_theo_doi", "summary":"...", "recommendations":["...", "..."], '
    '"key_signals":["...", "..."], "disclaimer":"..."}.\n'
    "Giu moi cau trong recommendations/key_signals TOI DA 150 ky tu, summary TOI DA 500 ky tu.\n"
    "Disclaimer LUON LUON la: "
    f'"{DEFAULT_DISCLAIMER}"'
)


class AssessmentService:
    """Service sinh assessment tu emotion (Google AI Studio).

    Sprint 19: RAG case memory (user history).
    Sprint 21: RAG knowledge base (WHO/APA docs).
    Sprint 30: Rate limiting + caching.
    """

    def __init__(
        self,
        client_factory=None,
        embedding_service: Optional[Any] = None,
        qdrant_service: Optional[Any] = None,
        knowledge_service: Optional[Any] = None,
        cache_repository: Optional[Any] = None,
        chat_cache_repository: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
    ):
        """
        Args:
            client_factory: Optional callable() -> google.genai.Client (cho test mock).
            embedding_service: Optional EmbeddingService (Sprint 18b) - cho RAG.
            qdrant_service: Optional QdrantService (Sprint 18b) - cho RAG.
            knowledge_service: Optional KnowledgeService (Sprint 21) - cho knowledge RAG.
            cache_repository: Optional AssessmentCacheRepository - cho assessment semantic cache.
            chat_cache_repository: Optional ChatCacheRepository - cho chat exact cache.
            rate_limiter: Optional RateLimiter - cho rate limiting.
        """
        self._client = None
        self._client_factory = client_factory
        # Sprint 19: RAG optional - neu None -> skip RAG
        self._embedding_service = embedding_service
        self._qdrant_service = qdrant_service
        # Sprint 21: Knowledge RAG
        self._knowledge_service = knowledge_service
        # Caches
        self._assessment_cache_repo = cache_repository
        self._chat_cache_repo = chat_cache_repository
        # Rate limiter
        self._rate_limiter = rate_limiter

    def _get_client(self):
        """Lazy init Google GenAI client."""
        if self._client is not None:
            return self._client

        settings = get_settings().google_ai
        if not settings.api_key:
            logger.warning("GOOGLE_API_KEY rong -> AI se tra fallback.")
            return None

        if self._client_factory is not None:
            self._client = self._client_factory()
            return self._client

        try:
            from google import genai
            self._client = genai.Client(api_key=settings.api_key)
            logger.info("Google GenAI client initialized (model=%s)", settings.model)
            return self._client
        except Exception as exc:
            logger.exception("Google GenAI init failed: %s", exc)
            return None

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _call_gemini(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Goi Gemini (retry 3 lan). Tra content string.

        - user_prompt: Nội dung cần phân tích.
        - system_prompt: Optional system prompt (default: SYSTEM_PROMPT).
        - max_output_tokens=4096: tranh bi cat ngang response (Gemini 3.x can
          budget lon hon de hoan thanh JSON schema).
        - Check finish_reason: neu bi MAX_TOKENS -> raise de retry/ fallback.
        """
        prompt = system_prompt or SYSTEM_PROMPT

        def _sync_call():
            from app.core.gemini_rotator import get_gemini_rotator
            rotator = get_gemini_rotator()

            def _execute(client, model):
                return client.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config={
                        "system_instruction": prompt,
                        "response_mime_type": "application/json",
                        "temperature": 0.3,
                        "max_output_tokens": 4096,
                    },
                )

            resp, model_used, key_used = rotator.execute_with_failover(_execute)
            text = resp.text or ""
            self._last_model_used = model_used
            # Check finish_reason (STOP = OK, MAX_TOKENS/SAFETY = fail)
            finish = None
            try:
                if resp.candidates:
                    finish = str(resp.candidates[0].finish_reason)
            except Exception:
                pass
            if not text:
                raise RuntimeError(f"Gemini tra response rong (finish={finish})")
            if finish and finish not in ("FinishReason.STOP", "STOP", "FinishReason.MAX_TOKENS", "MAX_TOKENS"):
                # SAFETY, RECITATION, BLOCKLIST, OTHER -> fail
                raise RuntimeError(f"Gemini finish_reason khong hop le: {finish}")
            return text

        return await asyncio.to_thread(_sync_call)

    @staticmethod
    def _safe_parse_json(content: str) -> dict:
        """Parse JSON tu Gemini, defensive neu response bi cat ngang.

        Gemini 3.x thinh thoang tra response khong close bracket khi het token.
        Tu dem so brackets mo/dong va them closing tuong ung.
        """
        text = content.strip()

        # Strip markdown fences neu co (```json ... ```)
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text else text
            text = text.lstrip("json").strip()
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0].strip()

        # Thu parse truc tiep
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Dem brackets mo/dong de biet can them gi
        # (khong tinh brackets trong string "...")
        def count_brackets(s: str):
            in_string = False
            escape = False
            opens = {"[": 0, "{": 0}
            closes = {"]": 0, "}": 0}
            for ch in s:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch in "[{":
                    opens[ch] += 1
                elif ch in "]}":
                    closes[ch] += 1
            return opens, closes

        opens, closes = count_brackets(text)
        # Can them: "[": opens["["] - closes["["], ...
        missing = ""
        # Add theo thu tu: dong object truoc, array sau
        # Vi JSON cuoi cung bao gio cung dong } nen them object closings truoc
        missing_close_brace = opens["{"] - closes["}"]
        missing_close_bracket = opens["["] - closes["]"]

        # Try them theo nhieu to hop (thuong chi 1-2 bracket)
        for extra in range(8):
            for _ in range(missing_close_bracket):
                missing += "]"
            for _ in range(missing_close_brace):
                missing += "}"
            try:
                return json.loads(text + missing)
            except json.JSONDecodeError:
                # Back off 1 bracket va thu lai
                if missing:
                    missing = missing[:-1]
                else:
                    break

        # Cuoi cung: extract { ... } substring (cat text theo first { va last })
        start = text.find("{")
        if start >= 0:
            truncated = text[start:]
            for extra in range(8):
                missing = "]" * (opens["["] - closes["]"]) + "}" * (opens["{"] - closes["}"])
                try:
                    return json.loads(truncated + missing[: extra + 1])
                except json.JSONDecodeError:
                    continue

        raise json.JSONDecodeError("Cannot parse Gemini response as JSON", text, 0)

    async def _build_rag_context(
        self, emotion: EmotionResult, user_id: str
    ) -> str:
        """Sprint 19: Lay top-K similar emotion snapshots tu Qdrant.

        Fail-soft: bat ky loi nao -> tra "" (skip RAG, van chay Gemini binh thuong).
        """
        if self._embedding_service is None or self._qdrant_service is None:
            return ""
        try:
            vector = await self._embedding_service.embed_emotion_snapshot(emotion)
            hits = await asyncio.to_thread(
                self._qdrant_service.search_similar,
                user_id=user_id,
                query_vector=vector,
                top_k=RAG_TOP_K,
            )
            if not hits:
                return ""
            # Format context (khong PII - chi emotion pattern + risk level)
            lines = ["Lich su cam xuc gan day cua user (top similar):"]
            for i, h in enumerate(hits, 1):
                lines.append(
                    f"{i}. dominant={h.get('dominant_emotion', '?')}, "
                    f"confidence={h.get('confidence', '?')}, "
                    f"risk_level={h.get('risk_level', '?')}, "
                    f"emotion_id={h.get('emotion_id', '?')}"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("RAG context build failed (skip): %s", exc)
            return ""

    async def _build_knowledge_context(self, emotion: EmotionResult) -> str:
        """Sprint 21: Search knowledge base (WHO/APA docs) gan voi emotion.

        Fail-soft: bat ky loi nao -> tra "" (skip knowledge RAG).
        """
        if self._knowledge_service is None:
            return ""
        try:
            # Query text: emotion JSON (tu emotion_payload)
            emotions = emotion.emotions.model_dump()
            query_text = (
                f"Emotion: {emotion.dominant_emotion} "
                f"(confidence={emotion.confidence:.2f}). "
                f"Scores: " + " ".join(
                    f"{k}={v:.1f}" for k, v in emotions.items()
                )
            )
            hits = await self._knowledge_service.search(
                query_text=query_text,
                top_k=KNOWLEDGE_TOP_K,
            )
            if not hits:
                return ""
            lines = ["Kien thuc y khoa / tam ly lien quan (knowledge RAG):"]
            for i, h in enumerate(hits, 1):
                title = h.get("title", "?")
                content = h.get("content", "")
                # Truncate content cho fit context window
                snippet = content[:280] + "..." if len(content) > 280 else content
                lines.append(f"{i}. [{h.get('source', '?')}] {title}\n   {snippet}")
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("Knowledge RAG context build failed (skip): %s", exc)
            return ""

    # ==========================================
    # Assessment Semantic Cache
    # ==========================================

    async def _check_assessment_cache(
        self,
        emotion: EmotionResult,
        user_id: Optional[str],
    ) -> Optional[AIAssessmentResult]:
        """Check assessment cache before calling Gemini.

        Uses deterministic hash of emotion values (rounded) for cache key.
        This enables cache hits for similar emotion inputs.

        Args:
            emotion: EmotionResult from DeepFace
            user_id: Optional user ID (stored for analytics)

        Returns:
            AIAssessmentResult if cache hit, None if miss
        """
        if self._assessment_cache_repo is None:
            return None

        try:
            # Generate cache key from emotion values
            emotions = emotion.emotions.model_dump()
            cache_key = self._assessment_cache_repo.generate_cache_key(
                emotions=emotions,
                dominant_emotion=emotion.dominant_emotion,
                confidence=emotion.confidence,
            )

            # Try to get cached result
            cached = self._assessment_cache_repo.get(cache_key)
            if cached is None:
                return None

            # Convert cached dict back to AIAssessmentResult
            return AIAssessmentResult.model_validate(cached)

        except Exception as exc:
            logger.warning("Assessment cache check failed (skip cache): %s", exc)
            return None

    async def _save_assessment_cache(
        self,
        emotion: EmotionResult,
        result: AIAssessmentResult,
        user_id: Optional[str],
    ) -> None:
        """Save assessment result to cache.

        Args:
            emotion: EmotionResult (for generating cache key)
            result: AIAssessmentResult to cache
            user_id: Optional user ID (stored for analytics)
        """
        if self._assessment_cache_repo is None:
            return

        try:
            emotions = emotion.emotions.model_dump()
            cache_key = self._assessment_cache_repo.generate_cache_key(
                emotions=emotions,
                dominant_emotion=emotion.dominant_emotion,
                confidence=emotion.confidence,
            )

            # Save to Firestore cache
            self._assessment_cache_repo.save(
                cache_key=cache_key,
                result=result.model_dump(),
                emotions=emotions,
                dominant_emotion=emotion.dominant_emotion,
                confidence=emotion.confidence,
                user_id=user_id,
            )
            logger.debug("Saved assessment to cache (key=%s)", cache_key[:8])

        except Exception as exc:
            logger.warning("Assessment cache save failed (non-critical): %s", exc)

    # ==========================================
    # Rate Limiting
    # ==========================================

    def _check_rate_limit(self, user_id: str) -> tuple[bool, Optional[str]]:
        """Check rate limit before AI call.

        Args:
            user_id: User ID

        Returns:
            (allowed, error_message)
        """
        if self._rate_limiter is None:
            return True, None

        try:
            result = self._rate_limiter.check(user_id)
            if not result["allowed"]:
                return False, result["reason"]
            return True, None
        except Exception as exc:
            logger.warning("Rate limit check failed (allowing): %s", exc)
            return True, None

    def _record_rate_limit(self, user_id: str) -> None:
        """Record AI call in rate limiter.

        Args:
            user_id: User ID
        """
        if self._rate_limiter is None:
            return

        try:
            self._rate_limiter.record(user_id)
        except Exception as exc:
            logger.warning("Rate limit record failed (non-critical): %s", exc)

    async def generate(
        self,
        emotion: EmotionResult,
        user_id: Optional[str] = None,
        skip_cache: bool = False,
    ) -> AIAssessmentResult:
        """
        Sinh AI assessment tu EmotionResult.

        Pipeline:
        1. Check assessment cache (semantic match by emotion hash)
        2. If cache hit -> return cached result
        3. If cache miss:
           - Build user prompt + RAG context
           - Call Gemini (retry 3 lan)
           - Save to cache
           - Return result
        4. Errors -> fallback

        Args:
            emotion: EmotionResult from DeepFace
            user_id: Optional user ID (for RAG history)
            skip_cache: Force bypass cache (for testing)
        """
        settings = get_settings().google_ai
        if not settings.api_key:
            return _fallback_assessment("Chua cau hinh GOOGLE_API_KEY.")

        # ==========================================
        # Step 1: Check cache (unless skip_cache)
        # ==========================================
        if not skip_cache:
            cache_result = await self._check_assessment_cache(emotion, user_id)
            if cache_result is not None:
                logger.info(
                    "Assessment CACHE HIT (dominant=%s, confidence=%.2f)",
                    emotion.dominant_emotion, emotion.confidence,
                )
                return cache_result

        # ==========================================
        # Step 2: Check rate limit (before Gemini call)
        # ==========================================
        effective_user_id = user_id or "anonymous"
        allowed, error_msg = self._check_rate_limit(effective_user_id)
        if not allowed:
            logger.warning("Rate limit exceeded for user %s: %s", effective_user_id, error_msg)
            return _fallback_assessment(f"Quota exceeded: {error_msg}")

        # ==========================================
        # Step 3: Cache miss - generate new assessment
        # ==========================================
        logger.info(
            "Assessment CACHE MISS - calling Gemini (dominant=%s)",
            emotion.dominant_emotion,
        )

        # Build user prompt (chi emotion data, KHONG co user_id / image_url)
        user_payload = {
            "emotions": emotion.emotions.model_dump(),
            "dominant_emotion": emotion.dominant_emotion,
            "confidence": emotion.confidence,
            "reliability_level": getattr(emotion, "reliability_level", "unknown"),
            "face_confidence": getattr(emotion, "face_confidence", None),
            "face_count": getattr(emotion, "face_count", None),
            "warnings": getattr(emotion, "warnings", []),
            "analyzed_at": (
                emotion.analyzed_at.isoformat() + "Z"
                if emotion.analyzed_at
                else None
            ),
        }
        user_prompt = (
            "Emotion data (JSON): " + json.dumps(user_payload, ensure_ascii=False)
            + "\n\nLUU Y: Day chi la phan tich tu hinh anh, khong phai chan doan tam than. "
            + "Hay danh gia nguy co dua tren tin hieu nay."
        )

        # Sprint 19: RAG inject (fail-soft)
        if user_id is not None:
            rag_context = await self._build_rag_context(emotion, user_id)
            if rag_context:
                user_prompt = (
                    user_prompt
                    + "\n\n"
                    + rag_context
                    + "\n\nHay can cu vao lich su tren de danh gia xu huong va dua khuyen nghi phu hop."
                )

        # Sprint 21: Knowledge RAG inject (fail-soft)
        knowledge_context = await self._build_knowledge_context(emotion)
        if knowledge_context:
            user_prompt = (
                user_prompt
                + "\n\n"
                + knowledge_context
                + "\n\nHay tham khao kien thuc y khoa/tam ly tren de dua canh y khoa chinh xac."
            )

        try:
            content = await self._call_gemini(user_prompt)
            data = self._safe_parse_json(content)
            # Ensure disclaimer luon la constant (khong trust AI)
            data["disclaimer"] = DEFAULT_DISCLAIMER
            # Attach model + prompt version (audit trail)
            data["ai_model"] = getattr(self, "_last_model_used", None)
            data["ai_prompt_version"] = AI_PROMPT_VERSION
            # Normalize risk_level defensively
            if "risk_level" in data:
                rl = str(data["risk_level"]).lower().strip()
                if rl in ("moderate", "trung_binh"):
                    data["risk_level"] = "medium"
                elif rl in ("critical", "nguy_cap", "bao_dong"):
                    data["risk_level"] = "high"
                elif rl not in ("low", "medium", "high", "can_theo_doi"):
                    data["risk_level"] = "can_theo_doi"

            # Build result
            result = AIAssessmentResult.model_validate(data)

            # ==========================================
            # Step 4: Record rate limit + save to cache
            # ==========================================
            self._record_rate_limit(effective_user_id)
            await self._save_assessment_cache(emotion, result, user_id)

            return result

        except Exception as exc:
            logger.warning("Gemini call failed (fallback): %s", exc)
            return _fallback_assessment("Loi Google AI.")

    async def analyze_chat_text(
        self,
        text: str,
        skip_cache: bool = False,
        user_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Phân tích chat text và trả về structured analysis.

        Dùng cho Module 4: AI Text Analysis.

        Flow:
        1. Check chat cache (exact match by text hash)
        2. If cache hit -> return cached result
        3. If cache miss:
           - Call Gemini
           - Save to cache
           - Return result
        4. Errors -> fallback

        Args:
            text: Tin nhắn chat của user.
            skip_cache: Force bypass cache (for testing)

        Returns:
            Dict với 8 signals theo spec, hoặc None nếu fail.
        """
        if not text or not text.strip():
            return None

        settings = get_settings().google_ai
        if not settings.api_key:
            logger.warning("GOOGLE_API_KEY rong -> Chat analysis fallback")
            return self._fallback_chat_analysis()

        # ==========================================
        # Step 1: Check chat cache
        # ==========================================
        if not skip_cache and self._chat_cache_repo is not None:
            cached = self._chat_cache_repo.get_by_text(text)
            if cached is not None:
                logger.info("Chat analysis CACHE HIT (text_len=%d)", len(text))
                return cached

        logger.info("Chat analysis CACHE MISS - calling Gemini")

        # ==========================================
        # Step 2: Check rate limit (before Gemini call)
        # ==========================================
        # Use user_id for rate limiting, fallback to "anonymous" if not provided
        rate_key = user_id if user_id else "anonymous"
        allowed, error_msg = self._check_rate_limit(rate_key)
        if not allowed:
            logger.warning("Rate limit exceeded for chat: %s", error_msg)
            return self._fallback_chat_analysis()

        # ==========================================
        # Step 3: Cache miss - call Gemini
        # ==========================================
        user_prompt = f"Analyze this message:\n\n{text}"

        try:
            content = await self._call_gemini(
                user_prompt,
                system_prompt=CHAT_ANALYSIS_PROMPT,
            )
            data = self._safe_parse_json(content)

            # Validate structure
            required_keys = [
                "stress_level", "fatigue_signal", "motivation_level",
                "work_avoidance_signal", "sleep_problem_signal",
                "emotional_negative_signal", "workload_signal",
                "burnout_related_signal"
            ]
            for key in required_keys:
                if key not in data:
                    data[key] = {"score": 0, "evidence": "Analysis structure incomplete"}

            # Ensure arrays
            data["detected_signals"] = data.get("detected_signals", [])
            data["important_phrases"] = data.get("important_phrases", [])
            data["uncertainty"] = data.get("uncertainty", 0.5)

            # Attach model info
            data["ai_model"] = settings.model
            data["ai_prompt_version"] = AI_PROMPT_VERSION

            logger.info(
                "Chat analysis done: stress=%s, burnout_signal=%s",
                data.get("stress_level", {}).get("score"),
                data.get("burnout_related_signal", {}).get("score"),
            )

            # ==========================================
            # Step 4: Record rate limit + save to cache
            # ==========================================
            self._record_rate_limit("anonymous")
            if self._chat_cache_repo is not None:
                try:
                    self._chat_cache_repo.save_by_text(text, data)
                    logger.debug("Saved chat analysis to cache")
                except Exception as exc:
                    logger.warning("Chat cache save failed (non-critical): %s", exc)

            return data

        except Exception as exc:
            logger.warning("Chat analysis failed (fallback): %s", exc)
            return self._fallback_chat_analysis()

    def _fallback_chat_analysis(self) -> dict:
        """Fallback chat analysis khi AI fail."""
        return {
            "stress_level": {"score": 0, "evidence": "Unable to analyze"},
            "fatigue_signal": {"score": 0, "evidence": "Unable to analyze"},
            "motivation_level": {"score": 50, "evidence": "Unable to analyze"},
            "work_avoidance_signal": {"score": 0, "evidence": "Unable to analyze"},
            "sleep_problem_signal": {"score": 0, "evidence": "Unable to analyze"},
            "emotional_negative_signal": {"score": 0, "evidence": "Unable to analyze"},
            "workload_signal": {"score": 0, "evidence": "Unable to analyze"},
            "burnout_related_signal": {"score": 0, "evidence": "Unable to analyze"},
            "detected_signals": [],
            "important_phrases": [],
            "uncertainty": 1.0,
            "ai_model": None,
            "ai_prompt_version": AI_PROMPT_VERSION,
        }


# ==========================================
# Chat Analysis Prompt (Module 4)
# ==========================================

CHAT_ANALYSIS_PROMPT = """You are a text analysis component inside a Burnout Risk Screening System.
Your task is to analyze the semantic content of a user's message and extract signals relevant to burnout risk.

IMPORTANT SAFETY RULES:
1. Do NOT diagnose any mental disorder.
2. Do NOT claim that the user has burnout, depression, anxiety, or another medical condition.
3. Do NOT provide a medical diagnosis.
4. Only identify observable semantic signals from the user's text.
5. If the text does not contain enough evidence, return low/unknown values.
6. Do not infer information that is not present in the text.
7. Your output will be used as ONE input for a separate Burnout Engine.
8. You must NOT calculate the final Burnout Score.
9. You must NOT determine the final Burnout Risk.
10. Return structured JSON only.

Output JSON (score: 0-100, evidence: explanation based on user's text):
{
  "stress_level": {"score": 0-100, "evidence": ""},
  "fatigue_signal": {"score": 0-100, "evidence": ""},
  "motivation_level": {"score": 0-100, "evidence": ""},
  "work_avoidance_signal": {"score": 0-100, "evidence": ""},
  "sleep_problem_signal": {"score": 0-100, "evidence": ""},
  "emotional_negative_signal": {"score": 0-100, "evidence": ""},
  "workload_signal": {"score": 0-100, "evidence": ""},
  "burnout_related_signal": {"score": 0-100, "evidence": ""},
  "detected_signals": [],
  "important_phrases": [],
  "uncertainty": 0.0-1.0
}"""


# ==========================================
# Singleton
# ==========================================

_assessment_service: Optional[AssessmentService] = None


def get_assessment_service() -> AssessmentService:
    """Lay AssessmentService singleton.

    Ghi chú: Qdrant DB / Vector RAG đã được lược bỏ theo yêu cầu.
    Hệ thống sử dụng thuần túy Chat History & Firestore.
    """
    global _assessment_service
    if _assessment_service is None:
        try:
            from app.modules.assessment.repositories.assessment_cache_repository import (
                get_assessment_cache_repository,
            )
            from app.modules.chat.repositories.chat_cache_repository import (
                get_chat_cache_repository,
            )
            from app.modules.assessment.services.rate_limiter import (
                get_rate_limiter,
            )
            assessment_cache = get_assessment_cache_repository()
            chat_cache = get_chat_cache_repository()
            rate_limiter = get_rate_limiter()
        except Exception:
            assessment_cache = None
            chat_cache = None
            rate_limiter = None
        _assessment_service = AssessmentService(
            embedding_service=None,
            qdrant_service=None,
            knowledge_service=None,
            cache_repository=assessment_cache,
            chat_cache_repository=chat_cache,
            rate_limiter=rate_limiter,
        )
    return _assessment_service
