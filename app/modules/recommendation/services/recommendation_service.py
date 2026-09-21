"""
==============================================================
File: recommendation_service.py

RecommendationService - Business logic cho recommendations.

Responsibilities:
- Generate recommendations từ BurnoutResult
- Apply personalization từ user profile
- Cache/reuse recommendations
- Save recommendation history
- Handle interactions

KHÔNG gọi AI cho simple recommendations.
AI chỉ được gọi khi rule engine + profile không đủ.
==============================================================
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.modules.burnout.models.burnout import BurnoutResult
from app.modules.burnout.repositories.burnout_repository import get_burnout_repository
from app.modules.recommendation.models.recommendation import (
    Recommendation,
    ActivityPlaceMapping,
    RecommendationHistory,
    RecommendationInteraction,
    UserRecommendationProfile,
    PlaceRecommendation,
)
from app.modules.recommendation.repositories.recommendation_repository import (
    get_recommendation_history_repository,
    get_recommendation_interaction_repository,
    get_user_recommendation_profile_repository,
    get_place_interaction_repository,
)

logger = logging.getLogger("burnout.recommendation.service")


# Activity to recommendation code mapping
ACTION_TO_ACTIVITY_CODE = {
    "sleep": "sleep",
    "workload": "workload",
    "stress": "stress",
    "emotion": "emotion",
    "behavior": "behavior",
}


class RecommendationService:
    """Service cho recommendation generation và personalization."""

    VALIDITY_HOURS = 24  # Recommendations valid for 24 hours

    def __init__(self):
        self._history_repo = get_recommendation_history_repository()
        self._interaction_repo = get_recommendation_interaction_repository()
        self._profile_repo = get_user_recommendation_profile_repository()

    def get_recommendations(
        self,
        assessment_id: str,
        user_id: str,
        burnout_result: Optional[BurnoutResult] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Lấy recommendations cho user.

        Flow:
        1. Check if existing recommendation is valid
        2. If valid and not force_refresh -> reuse
        3. If not valid or no existing -> generate new
        4. Apply personalization
        5. Save to history
        6. Return recommendations

        Args:
            assessment_id: Assessment ID
            user_id: User ID
            burnout_result: Optional BurnoutResult (nếu có sẵn)
            force_refresh: Force regenerate even if valid exists

        Returns:
            Dict với recommendations và metadata
        """
        # 1. Check for existing valid recommendation
        if not force_refresh:
            existing = self._history_repo.get_by_assessment(assessment_id)
            if existing and self._is_valid(existing):
                logger.info("Reusing existing recommendation for assessment %s", assessment_id)
                return self._build_response_from_history(existing, user_id, reuse=True)

        # 2. Need to generate new recommendations
        if burnout_result is None:
            # Load from burnout repository
            burnout_repo = get_burnout_repository()
            burnout_doc = burnout_repo.get_by_assessment(assessment_id)
            if not burnout_doc:
                raise ValueError(f"No burnout result for assessment {assessment_id}")
            # Convert to BurnoutResult-like structure
            burnout_result = self._dict_to_burnout_result(burnout_doc)

        # 3. Generate recommendations using rule engine
        recommendations = self._generate_recommendations(burnout_result)

        # 4. Apply personalization
        recommendations = self._apply_personalization(user_id, recommendations)

        # 5. Save to history
        history = RecommendationHistory(
            assessment_id=assessment_id,
            user_id=user_id,
            burnout_score=burnout_result.burnout_score,
            risk_level=burnout_result.risk_level,
            recommendations=[r.model_dump() for r in recommendations],
            validity_hours=self.VALIDITY_HOURS,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=self.VALIDITY_HOURS),
        )
        self._history_repo.save(history)

        logger.info(
            "Generated %d recommendations for assessment %s (score=%.1f)",
            len(recommendations), assessment_id, burnout_result.burnout_score,
        )

        # 6. Build response
        return {
            "assessment_id": assessment_id,
            "user_id": user_id,
            "burnout_score": burnout_result.burnout_score,
            "risk_level": burnout_result.risk_level,
            "recommendations": [r.model_dump() for r in recommendations],
            "is_reused": False,
            "generated_at": datetime.utcnow().isoformat(),
            "expires_at": history.expires_at.isoformat() if history.expires_at else None,
        }

    def record_interaction(
        self,
        user_id: str,
        assessment_id: str,
        recommendation_code: str,
        action: str,
        recommendation_title: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Ghi nhận user interaction với recommendation.

        Args:
            user_id: User ID
            assessment_id: Assessment ID
            recommendation_code: Activity code
            action: Interaction action
            recommendation_title: Optional title
            duration_minutes: Optional duration if completed
            notes: Optional notes

        Returns:
            Interaction ID
        """
        interaction = RecommendationInteraction(
            user_id=user_id,
            assessment_id=assessment_id,
            recommendation_code=recommendation_code,
            recommendation_title=recommendation_title,
            action=action,
            duration_minutes=duration_minutes,
            notes=notes,
            created_at=datetime.utcnow(),
        )
        interaction_id = self._interaction_repo.save(interaction)

        # Update user profile with affinity
        completed = action == "completed"
        self._profile_repo.update_activity_affinity(
            user_id=user_id,
            activity_code=recommendation_code,
            action=action,
            completed=completed,
        )

        logger.info(
            "Recorded interaction %s for user %s: %s (%s)",
            interaction_id, user_id, recommendation_code, action,
        )
        return interaction_id

    def get_user_profile(self, user_id: str) -> Optional[UserRecommendationProfile]:
        """Lấy user recommendation profile.

        Args:
            user_id: User ID

        Returns:
            UserRecommendationProfile hoặc None
        """
        profile_dict = self._profile_repo.get(user_id)
        if not profile_dict:
            return None
        return UserRecommendationProfile(**profile_dict)

    def _generate_recommendations(
        self,
        burnout_result: BurnoutResult,
    ) -> List[Recommendation]:
        """Generate recommendations using rule engine.

        Args:
            burnout_result: Burnout result

        Returns:
            List of Recommendations
        """
        # Import here to avoid circular dependency
        from app.modules.recommendation.services.recommendation_engine import (
            get_recommendation_engine,
        )

        engine = get_recommendation_engine()
        recs = engine.generate(burnout_result)

        # Add activity metadata
        enriched_recs = []
        for rec in recs:
            rec_dict = rec.model_dump()
            rec_dict = self._enrich_with_activity(rec_dict, rec.target_factor)
            enriched_recs.append(Recommendation(**rec_dict))

        return enriched_recs

    def _enrich_with_activity(
        self,
        rec_dict: Dict[str, Any],
        target_factor: Optional[str],
    ) -> Dict[str, Any]:
        """Enrich recommendation with activity metadata."""
        # Determine activity code from target factor
        activity_code = ACTION_TO_ACTIVITY_CODE.get(target_factor or "", "behavior")

        # Get place categories
        categories = ActivityPlaceMapping.get_categories(activity_code)

        # Get duration
        duration = ActivityPlaceMapping.get_duration(activity_code)

        # Get location required
        location_required = ActivityPlaceMapping.is_location_required(activity_code)

        rec_dict["activity_code"] = activity_code
        rec_dict["place_categories"] = categories
        rec_dict["duration_minutes"] = duration
        rec_dict["location_required"] = location_required

        return rec_dict

    def _apply_personalization(
        self,
        user_id: str,
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """Apply user personalization to recommendations.

        Args:
            user_id: User ID
            recommendations: List of base recommendations

        Returns:
            Personalized recommendations (sorted by affinity)
        """
        profile = self._profile_repo.get(user_id)

        if not profile:
            return recommendations

        preferred = profile.get("preferred_activities", {})
        avoided = profile.get("avoided_activities", {})

        if not preferred and not avoided:
            return recommendations

        # Score adjustments based on profile
        adjusted_recs = []
        for rec in recommendations:
            rec_dict = rec.model_dump()
            activity_code = rec_dict.get("activity_code", "")

            # Calculate adjustment
            adjustment = 0.0
            if activity_code in preferred:
                adjustment += preferred[activity_code] * 0.2  # Up to +20%
            if activity_code in avoided:
                adjustment -= avoided[activity_code] * 0.2  # Up to -20%

            rec_dict["_personalization_adjustment"] = adjustment
            adjusted_recs.append(Recommendation(**rec_dict))

        # Sort by: priority (high first) + personalization adjustment
        adjusted_recs.sort(
            key=lambda r: (
                -self._priority_score(r.priority),
                -(r.model_dump().get("_personalization_adjustment", 0)),
            )
        )

        return adjusted_recs

    def _priority_score(self, priority: str) -> int:
        """Convert priority to score for sorting."""
        scores = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
        return scores.get(priority, 0)

    def _is_valid(self, history: Dict[str, Any]) -> bool:
        """Check if recommendation history is still valid."""
        expires_at = history.get("expires_at")
        if not expires_at:
            # No expiry, check created_at
            created_at = history.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    try:
                        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        return datetime.utcnow() - created < timedelta(hours=self.VALIDITY_HOURS)
                    except Exception:
                        pass
            return False

        # Check expires_at
        if isinstance(expires_at, datetime):
            return expires_at > datetime.utcnow()
        if isinstance(expires_at, str):
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                return expiry > datetime.utcnow()
            except Exception:
                pass
        return False

    def _build_response_from_history(
        self,
        history: Dict[str, Any],
        user_id: str,
        reuse: bool = True,
    ) -> Dict[str, Any]:
        """Build response from existing history."""
        return {
            "assessment_id": history.get("assessment_id"),
            "user_id": user_id,
            "burnout_score": history.get("burnout_score"),
            "risk_level": history.get("risk_level"),
            "recommendations": history.get("recommendations", []),
            "is_reused": reuse,
            "generated_at": str(history.get("created_at", "")),
            "expires_at": str(history.get("expires_at", "")),
        }

    def _dict_to_burnout_result(self, doc: Dict[str, Any]) -> BurnoutResult:
        """Convert Firestore doc to BurnoutResult."""
        from app.modules.burnout.models.burnout import BurnoutFactor

        factors = []
        for f in doc.get("factors", []):
            factors.append(BurnoutFactor(**f))

        return BurnoutResult(
            burnout_score=doc.get("burnout_score", 0.0),
            data_completeness=doc.get("data_completeness", 0.0),
            risk_level=doc.get("risk_level", "unknown"),
            trend=doc.get("trend", "insufficient_data"),
            factors=factors,
            recommendations=doc.get("recommendations", []),
            analyzed_at=doc.get("analyzed_at", datetime.utcnow()),
        )


# ==========================================
# Singleton
# ==========================================

_recommendation_service: Optional[RecommendationService] = None


def get_recommendation_service() -> RecommendationService:
    """Get RecommendationService singleton."""
    global _recommendation_service
    if _recommendation_service is None:
        _recommendation_service = RecommendationService()
    return _recommendation_service
