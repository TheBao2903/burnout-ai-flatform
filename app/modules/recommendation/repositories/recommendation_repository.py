"""
==============================================================
File: recommendation_repository.py

Repositories cho Recommendation features:
- RecommendationHistory
- RecommendationInteraction
- UserRecommendationProfile
- PlaceInteraction

Firestore Collections:
- recommendation_history
- recommendation_interactions
- user_recommendation_profiles
- place_interactions
==============================================================
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.cloud import firestore

from app.core.firebase import FirestoreCollections, get_firebase
from app.modules.recommendation.models.recommendation import (
    RecommendationHistory,
    RecommendationInteraction,
    UserRecommendationProfile,
    PlaceInteraction,
)

logger = logging.getLogger("burnout.recommendation.repo")


class RecommendationHistoryRepository:
    """Repository cho RecommendationHistory."""

    COLLECTION_NAME = FirestoreCollections.RECOMMENDATION_HISTORY or "recommendation_history"

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(self.COLLECTION_NAME)

    def save(self, history: RecommendationHistory) -> str:
        """Lưu recommendation history.

        Args:
            history: RecommendationHistory instance

        Returns:
            Document ID
        """
        doc_ref = self.collection.document()
        data = {
            "assessment_id": history.assessment_id,
            "user_id": history.user_id,
            "burnout_score": history.burnout_score,
            "risk_level": history.risk_level,
            "recommendations": history.recommendations,
            "validity_hours": history.validity_hours,
            "created_at": firestore.SERVER_TIMESTAMP,
            "expires_at": firestore.SERVER_TIMESTAMP if history.expires_at else None,
        }
        doc_ref.set(data)
        logger.info(
            "Saved recommendation history %s for assessment %s",
            doc_ref.id, history.assessment_id,
        )
        return doc_ref.id

    def get_by_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Lấy recommendation history theo assessment.

        Args:
            assessment_id: Assessment ID

        Returns:
            History dict hoặc None
        """
        query = self.collection.where("assessment_id", "==", assessment_id).limit(1)
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def get_latest_valid(
        self,
        user_id: str,
        assessment_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Lấy recommendation history còn valid gần nhất.

        Args:
            user_id: User ID
            assessment_id: Optional assessment ID để exclude

        Returns:
            Valid history dict hoặc None
        """
        query = self.collection.where("user_id", "==", user_id)
        if assessment_id:
            query = query.where("assessment_id", "!=", assessment_id)
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(10)

        now = datetime.utcnow()
        for doc in query.stream():
            data = doc.to_dict()
            expires_at = data.get("expires_at")
            if expires_at:
                # Check if expired
                if isinstance(expires_at, datetime) and expires_at < now:
                    continue
                if isinstance(expires_at, str):
                    try:
                        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        if exp < now:
                            continue
                    except Exception:
                        pass
            data["id"] = doc.id
            return data
        return None

    def list_by_user(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Lấy recommendation histories của user.

        Args:
            user_id: User ID
            limit: Max results

        Returns:
            List of history dicts
        """
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def delete_by_assessment(self, assessment_id: str) -> int:
        """Xóa recommendation histories của một assessment.

        Returns:
            Số docs đã xóa
        """
        docs = self.collection.where("assessment_id", "==", assessment_id).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        return count


class RecommendationInteractionRepository:
    """Repository cho RecommendationInteraction."""

    COLLECTION_NAME = FirestoreCollections.RECOMMENDATION_INTERACTIONS or "recommendation_interactions"

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(self.COLLECTION_NAME)

    def save(self, interaction: RecommendationInteraction) -> str:
        """Lưu recommendation interaction.

        Args:
            interaction: RecommendationInteraction instance

        Returns:
            Document ID
        """
        doc_ref = self.collection.document()
        data = {
            "user_id": interaction.user_id,
            "assessment_id": interaction.assessment_id,
            "recommendation_code": interaction.recommendation_code,
            "recommendation_title": interaction.recommendation_title,
            "action": interaction.action,
            "duration_minutes": interaction.duration_minutes,
            "notes": interaction.notes,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        doc_ref.set(data)
        logger.info(
            "Saved recommendation interaction %s for user %s",
            doc_ref.id, interaction.user_id,
        )
        return doc_ref.id

    def get_by_user(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lấy interactions của user.

        Returns:
            List of interaction dicts
        """
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def count_by_user(self, user_id: str) -> int:
        """Đếm interactions của user.

        Returns:
            Total count
        """
        try:
            query = self.collection.where("user_id", "==", user_id)
            agg = query.count()
            results = agg.get()
            return int(results[0][0].value)
        except Exception as exc:
            logger.warning("count_by_user failed: %s", exc)
            return 0

    def get_interactions_for_activity(
        self,
        user_id: str,
        activity_code: str,
    ) -> List[Dict[str, Any]]:
        """Lấy interactions cho một activity.

        Returns:
            List of interactions
        """
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .where("recommendation_code", "==", activity_code)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(20)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def delete_by_assessment(self, assessment_id: str) -> int:
        """Xóa interactions của một assessment.

        Returns:
            Số docs đã xóa
        """
        docs = self.collection.where("assessment_id", "==", assessment_id).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        return count


class UserRecommendationProfileRepository:
    """Repository cho UserRecommendationProfile."""

    COLLECTION_NAME = FirestoreCollections.USER_RECOMMENDATION_PROFILES or "user_recommendation_profiles"

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(self.COLLECTION_NAME)

    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy profile của user.

        Returns:
            Profile dict hoặc None
        """
        doc = self.collection.document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def save(self, profile: UserRecommendationProfile) -> str:
        """Lưu user recommendation profile.

        Args:
            profile: UserRecommendationProfile instance

        Returns:
            User ID (document ID)
        """
        data = {
            "user_id": profile.user_id,
            "preferred_activities": profile.preferred_activities,
            "avoided_activities": profile.avoided_activities,
            "preferred_place_types": profile.preferred_place_types,
            "avoided_place_types": profile.avoided_place_types,
            "total_interactions": profile.total_interactions,
            "total_completed": profile.total_completed,
            "last_interaction_at": firestore.SERVER_TIMESTAMP,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        self.collection.document(profile.user_id).set(data)
        logger.info("Saved user recommendation profile for user %s", profile.user_id)
        return profile.user_id

    def upsert(self, profile: UserRecommendationProfile) -> str:
        """Upsert user recommendation profile.

        Args:
            profile: UserRecommendationProfile instance

        Returns:
            User ID
        """
        existing = self.get(profile.user_id)
        if existing:
            # Update only provided fields
            update_data = {
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
            if profile.preferred_activities:
                update_data["preferred_activities"] = profile.preferred_activities
            if profile.avoided_activities:
                update_data["avoided_activities"] = profile.avoided_activities
            if profile.preferred_place_types:
                update_data["preferred_place_types"] = profile.preferred_place_types
            if profile.avoided_place_types:
                update_data["avoided_place_types"] = profile.avoided_place_types
            if profile.total_interactions is not None:
                update_data["total_interactions"] = profile.total_interactions
            if profile.total_completed is not None:
                update_data["total_completed"] = profile.total_completed
            self.collection.document(profile.user_id).update(update_data)
            logger.info("Updated user recommendation profile for user %s", profile.user_id)
        else:
            self.save(profile)
        return profile.user_id

    def update_activity_affinity(
        self,
        user_id: str,
        activity_code: str,
        action: str,
        completed: bool = False,
    ) -> None:
        """Cập nhật activity affinity dựa trên interaction.

        Args:
            user_id: User ID
            activity_code: Activity code
            action: Interaction action (viewed, saved, completed, etc.)
            completed: Whether activity was completed
        """
        profile = self.get(user_id)
        if not profile:
            profile = UserRecommendationProfile(user_id=user_id)
            profile_dict = {}
        else:
            profile_dict = dict(profile)

        # Update preferred activities
        preferred = profile_dict.get("preferred_activities", {})
        avoided = profile_dict.get("avoided_activities", {})

        # Calculate affinity change
        if action in ("completed", "liked", "saved"):
            # Increase affinity
            current = preferred.get(activity_code, 0.5)
            preferred[activity_code] = min(1.0, current + 0.1)
            # Decrease avoided
            if activity_code in avoided:
                avoided[activity_code] = max(0.0, avoided[activity_code] - 0.1)
        elif action in ("dismissed", "disliked"):
            # Decrease affinity
            current = preferred.get(activity_code, 0.5)
            preferred[activity_code] = max(0.0, current - 0.1)
            # Increase avoided
            avoided[activity_code] = avoided.get(activity_code, 0.0) + 0.1

        profile_dict["preferred_activities"] = preferred
        profile_dict["avoided_activities"] = avoided
        profile_dict["total_interactions"] = profile_dict.get("total_interactions", 0) + 1
        if completed:
            profile_dict["total_completed"] = profile_dict.get("total_completed", 0) + 1

        profile_dict["user_id"] = user_id
        self.upsert(UserRecommendationProfile(**profile_dict))


class PlaceInteractionRepository:
    """Repository cho PlaceInteraction."""

    COLLECTION_NAME = FirestoreCollections.PLACE_INTERACTIONS or "place_interactions"

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(self.COLLECTION_NAME)

    def save(self, interaction: PlaceInteraction) -> str:
        """Lưu place interaction.

        Args:
            interaction: PlaceInteraction instance

        Returns:
            Document ID
        """
        doc_ref = self.collection.document()
        data = {
            "user_id": interaction.user_id,
            "assessment_id": interaction.assessment_id,
            "place_id": interaction.place_id,
            "place_name": interaction.place_name,
            "activity_type": interaction.activity_type,
            "action": interaction.action,
            "rating": interaction.rating,
            "notes": interaction.notes,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        doc_ref.set(data)
        logger.info(
            "Saved place interaction %s for user %s",
            doc_ref.id, interaction.user_id,
        )
        return doc_ref.id

    def get_by_user(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lấy interactions của user.

        Returns:
            List of interaction dicts
        """
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def update_place_type_affinity(
        self,
        user_id: str,
        activity_code: str,
        categories: List[str],
        action: str,
    ) -> None:
        """Cập nhật place type affinity dựa trên interaction.

        Args:
            user_id: User ID
            activity_code: Activity code (for reference)
            categories: Geoapify categories
            action: Interaction action
        """
        profile_repo = UserRecommendationProfileRepository()
        profile = profile_repo.get(user_id)

        if not profile:
            return

        preferred = profile.get("preferred_place_types", {})
        avoided = profile.get("avoided_place_types", {})

        for category in categories:
            if action in ("saved", "visited", "reviewed"):
                current = preferred.get(category, 0.5)
                preferred[category] = min(1.0, current + 0.1)
            elif action == "dismissed":
                current = preferred.get(category, 0.5)
                preferred[category] = max(0.0, current - 0.1)
                avoided[category] = avoided.get(category, 0.0) + 0.05

        profile["preferred_place_types"] = preferred
        profile["avoided_place_types"] = avoided
        profile_repo.upsert(UserRecommendationProfile(**profile))


# ==========================================
# Singleton instances
# ==========================================

_history_repo: Optional[RecommendationHistoryRepository] = None
_interaction_repo: Optional[RecommendationInteractionRepository] = None
_profile_repo: Optional[UserRecommendationProfileRepository] = None
_place_interaction_repo: Optional[PlaceInteractionRepository] = None


def get_recommendation_history_repository() -> RecommendationHistoryRepository:
    global _history_repo
    if _history_repo is None:
        _history_repo = RecommendationHistoryRepository()
    return _history_repo


def get_recommendation_interaction_repository() -> RecommendationInteractionRepository:
    global _interaction_repo
    if _interaction_repo is None:
        _interaction_repo = RecommendationInteractionRepository()
    return _interaction_repo


def get_user_recommendation_profile_repository() -> UserRecommendationProfileRepository:
    global _profile_repo
    if _profile_repo is None:
        _profile_repo = UserRecommendationProfileRepository()
    return _profile_repo


def get_place_interaction_repository() -> PlaceInteractionRepository:
    global _place_interaction_repo
    if _place_interaction_repo is None:
        _place_interaction_repo = PlaceInteractionRepository()
    return _place_interaction_repo
