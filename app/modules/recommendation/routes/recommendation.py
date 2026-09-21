"""
==============================================================
File: recommendation.py

Recommendation Routes - API endpoints cho Recommendations.

GET  /api/v1/assessments/{id}/recommendations     - Lấy recommendations
POST /api/v1/assessments/{id}/recommendations     - Refresh recommendations
POST /api/v1/assessments/{id}/recommendations/interaction - Record interaction
GET  /api/v1/assessments/{id}/recommendations/places - Tìm địa điểm
POST /api/v1/assessments/{id}/recommendations/places/interaction - Record place interaction
GET  /api/v1/users/me/recommendation-profile      - Lấy user profile
==============================================================
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.modules.assessment.repositories.assessment_session_repository import (
    get_assessment_session_repository,
)
from app.modules.burnout.repositories.burnout_repository import (
    get_burnout_repository,
)
from app.modules.recommendation.services.recommendation_service import (
    get_recommendation_service,
)
from app.modules.recommendation.services.place_recommendation_service import (
    get_place_recommendation_service,
    PlaceRecommendationError,
)

logger = logging.getLogger("burnout.recommendation.routes")

router = APIRouter(prefix="/api/v1/assessments", tags=["Recommendations"])


# ==========================================
# Request/Response Models
# ==========================================

class RecommendationResponse(BaseModel):
    """Response cho recommendations endpoint."""

    assessment_id: str
    user_id: str
    burnout_score: float
    risk_level: str
    recommendations: list
    is_reused: bool
    generated_at: Optional[str] = None
    expires_at: Optional[str] = None


class InteractionRequest(BaseModel):
    """Request cho record interaction."""

    recommendation_code: str = Field(..., description="Activity code")
    action: str = Field(..., description="Interaction action: viewed, saved, dismissed, started, completed, liked, disliked")
    recommendation_title: Optional[str] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None


class InteractionResponse(BaseModel):
    """Response sau khi record interaction."""

    message: str
    interaction_id: str


class PlaceSearchRequest(BaseModel):
    """Request cho search places."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    activity_type: str = Field(..., description="Activity type: outdoor_walk, nature, exercise, etc.")
    radius_meters: Optional[int] = Field(default=5000, ge=100, le=10000, description="Search radius")
    limit: Optional[int] = Field(default=10, ge=1, le=20, description="Number of places")
    lang: Optional[str] = Field(default="vi", description="Language code")


class PlaceResponse(BaseModel):
    """Response cho places endpoint."""

    assessment_id: str
    user_id: str
    activity_type: str
    categories: list
    search_location: dict
    places: list
    count: int
    message: str
    searched_at: str


class PlaceInteractionRequest(BaseModel):
    """Request cho record place interaction."""

    place_id: str = Field(..., description="Geoapify place ID")
    activity_type: str = Field(..., description="Activity type")
    action: str = Field(..., description="Action: viewed, clicked, saved, opened, dismissed, visited, reviewed")
    place_name: Optional[str] = None
    rating: Optional[float] = None
    notes: Optional[str] = None


class UserProfileResponse(BaseModel):
    """Response cho user recommendation profile."""

    user_id: str
    preferred_activities: dict
    avoided_activities: dict
    preferred_place_types: dict
    avoided_place_types: dict
    total_interactions: int
    total_completed: int


# ==========================================
# Dependencies
# ==========================================

def get_assessment_repo():
    return get_assessment_session_repository()


def get_burnout_repo():
    return get_burnout_repository()


def get_rec_service():
    return get_recommendation_service()


def get_place_service():
    return get_place_recommendation_service()


# ==========================================
# GET /api/v1/assessments/{id}/recommendations
# ==========================================

@router.get("/{assessment_id}/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    assessment_id: str,
    user: dict = Depends(get_current_user),
):
    """Lấy recommendations cho một assessment.

    Flow:
    1. Validate assessment exists & belongs to user
    2. Validate assessment has burnout result
    3. Check if existing recommendation is valid
    4. If valid -> reuse
    5. If not valid -> generate new
    6. Return recommendations
    """
    user_id = user["uid"]

    # 1. Verify ownership
    assessment_repo = get_assessment_repo()
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # 2. Check if has result
    if not assessment.get("status_detail", {}).get("has_result"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment has no burnout result. Run /analyze first.",
        )

    # 3. Get recommendations
    rec_service = get_rec_service()
    result = rec_service.get_recommendations(
        assessment_id=assessment_id,
        user_id=user_id,
    )

    return RecommendationResponse(**result)


# ==========================================
# POST /api/v1/assessments/{id}/recommendations
# ==========================================

@router.post("/{assessment_id}/recommendations", response_model=RecommendationResponse)
async def refresh_recommendations(
    assessment_id: str,
    user: dict = Depends(get_current_user),
):
    """Refresh recommendations (force regenerate).

    Chỉ dùng khi user muốn regenerate recommendations.
    """
    user_id = user["uid"]

    # Verify ownership
    assessment_repo = get_assessment_repo()
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # Get recommendations (force refresh)
    rec_service = get_rec_service()
    result = rec_service.get_recommendations(
        assessment_id=assessment_id,
        user_id=user_id,
        force_refresh=True,
    )

    return RecommendationResponse(**result)


# ==========================================
# POST /api/v1/assessments/{id}/recommendations/interaction
# ==========================================

@router.post("/{assessment_id}/recommendations/interaction", response_model=InteractionResponse)
async def record_recommendation_interaction(
    assessment_id: str,
    request: InteractionRequest,
    user: dict = Depends(get_current_user),
):
    """Record user interaction với recommendation.

    Actions: viewed, saved, dismissed, started, completed, liked, disliked
    """
    user_id = user["uid"]

    # Verify ownership
    assessment_repo = get_assessment_repo()
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # Record interaction
    rec_service = get_rec_service()
    interaction_id = rec_service.record_interaction(
        user_id=user_id,
        assessment_id=assessment_id,
        recommendation_code=request.recommendation_code,
        action=request.action,
        recommendation_title=request.recommendation_title,
        duration_minutes=request.duration_minutes,
        notes=request.notes,
    )

    return InteractionResponse(
        message=f"Recorded {request.action} interaction",
        interaction_id=interaction_id,
    )


# ==========================================
# GET /api/v1/assessments/{id}/recommendations/places
# ==========================================

@router.get("/{assessment_id}/recommendations/places", response_model=PlaceResponse)
async def search_places(
    assessment_id: str,
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
    activity_type: str = Query(..., description="Activity type"),
    radius_meters: Optional[int] = Query(default=5000, ge=100, le=10000),
    limit: Optional[int] = Query(default=10, ge=1, le=20),
    lang: Optional[str] = Query(default="vi"),
    user: dict = Depends(get_current_user),
):
    """Tìm địa điểm cho activity type.

    Flow:
    1. Validate assessment exists & belongs to user
    2. Map activity -> Geoapify categories
    3. Search places with Geoapify
    4. Apply personalization
    5. Return normalized places
    6. Record view interaction
    """
    user_id = user["uid"]

    # 1. Verify ownership
    assessment_repo = get_assessment_repo()
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # 2. Search places
    place_service = get_place_service()
    try:
        result = place_service.search_places(
            assessment_id=assessment_id,
            user_id=user_id,
            activity_type=activity_type,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            limit=limit,
            lang=lang,
        )
    except PlaceRecommendationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return PlaceResponse(**result)


# ==========================================
# POST /api/v1/assessments/{id}/recommendations/places/interaction
# ==========================================

@router.post("/{assessment_id}/recommendations/places/interaction", response_model=InteractionResponse)
async def record_place_interaction(
    assessment_id: str,
    request: PlaceInteractionRequest,
    user: dict = Depends(get_current_user),
):
    """Record user interaction với place.

    Actions: viewed, clicked, saved, opened, dismissed, visited, reviewed
    """
    user_id = user["uid"]

    # Verify ownership
    assessment_repo = get_assessment_repo()
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # Record interaction
    place_service = get_place_service()
    interaction_id = place_service.record_place_interaction(
        user_id=user_id,
        assessment_id=assessment_id,
        place_id=request.place_id,
        activity_type=request.activity_type,
        action=request.action,
        place_name=request.place_name,
        rating=request.rating,
        notes=request.notes,
    )

    return InteractionResponse(
        message=f"Recorded {request.action} for place",
        interaction_id=interaction_id,
    )


# ==========================================
# GET /api/v1/users/me/recommendation-profile
# ==========================================

user_profile_router = APIRouter(prefix="/api/v1/users/me", tags=["Recommendations"])


@user_profile_router.get("/recommendation-profile", response_model=UserProfileResponse)
async def get_user_recommendation_profile(
    user: dict = Depends(get_current_user),
):
    """Lấy user recommendation profile (personalization data)."""
    user_id = user["uid"]

    rec_service = get_rec_service()
    profile = rec_service.get_user_profile(user_id)

    if not profile:
        # Return empty profile
        return UserProfileResponse(
            user_id=user_id,
            preferred_activities={},
            avoided_activities={},
            preferred_place_types={},
            avoided_place_types={},
            total_interactions=0,
            total_completed=0,
        )

    return UserProfileResponse(
        user_id=profile.user_id,
        preferred_activities=profile.preferred_activities,
        avoided_activities=profile.avoided_activities,
        preferred_place_types=profile.preferred_place_types,
        avoided_place_types=profile.avoided_place_types,
        total_interactions=profile.total_interactions,
        total_completed=profile.total_completed,
    )


# ==========================================
# Weather Routes
# ==========================================

weather_router = APIRouter(prefix="/api/v1", tags=["Weather"])


# ==========================================
# Survey Routes (standalone - no assessment required)
# ==========================================

survey_router = APIRouter(prefix="/api/survey", tags=["Survey"])


class GeocodeRequest(BaseModel):
    """Request cho geocode endpoint."""
    address: str = Field(..., description="Address text to geocode")


class GeocodeResponse(BaseModel):
    """Response cho geocode endpoint."""
    latitude: float
    longitude: float
    formatted_address: str
    success: bool
    message: str


class SurveyPlaceSearchRequest(BaseModel):
    """Request cho survey place search."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    stress_level: int = Field(..., ge=1, le=10)
    radius_meters: Optional[int] = Field(default=3000, ge=100, le=10000)
    limit: Optional[int] = Field(default=10, ge=1, le=20)
    address: Optional[str] = Field(default=None, description="Địa chỉ để hiển thị")


class SurveyPlaceResponse(BaseModel):
    """Response cho survey place search."""
    places: list
    count: int
    searched_location: dict
    address: Optional[str] = None
    message: str


@survey_router.post("/geocode", response_model=GeocodeResponse)
async def geocode_address(
    request: GeocodeRequest,
):
    """Chuyển địa chỉ text thành tọa độ lat/lon.

    Sử dụng Nominatim (OpenStreetMap) - free, no API key.
    """
    from app.modules.recommendation.services.place_recommendation_service import (
        get_place_recommendation_service,
    )
    place_service = get_place_recommendation_service()

    try:
        result = place_service.geocode_address(request.address)
        if result:
            return GeocodeResponse(**result)
        return GeocodeResponse(
            latitude=0,
            longitude=0,
            formatted_address="",
            success=False,
            message="Không tìm thấy địa chỉ",
        )
    except Exception as e:
        logger.error("Geocode error: %s", e)
        return GeocodeResponse(
            latitude=0,
            longitude=0,
            formatted_address="",
            success=False,
            message=f"Lỗi: {str(e)}",
        )


@survey_router.post("/places", response_model=SurveyPlaceResponse)
async def search_places_for_survey(
    request: SurveyPlaceSearchRequest,
    user: dict = Depends(get_current_user),
):
    """Tìm địa điểm giảm stress cho survey (standalone).

    Không cần assessment_id, chỉ cần tọa độ và mức độ stress.
    """
    from app.modules.recommendation.services.place_recommendation_service import (
        get_place_recommendation_service,
    )
    place_service = get_place_recommendation_service()
    user_id = user["uid"]

    try:
        result = place_service.search_places_for_survey(
            user_id=user_id,
            latitude=request.latitude,
            longitude=request.longitude,
            stress_level=request.stress_level,
            radius_meters=request.radius_meters,
            limit=request.limit,
            address=request.address,
        )
        return SurveyPlaceResponse(**result)
    except Exception as e:
        logger.error("Survey places error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


class WeatherResponse(BaseModel):
    """Response cho weather endpoint."""

    latitude: float
    longitude: float
    weather: dict
    is_good_for_outdoor: bool


class ForecastResponse(BaseModel):
    """Response cho weather forecast endpoint."""

    latitude: float
    longitude: float
    forecasts: list
    count: int


class WeatherAdjustmentResponse(BaseModel):
    """Response cho weather adjustment endpoint."""

    activity_code: str
    weather: dict
    weather_adjustment: dict
    is_good_for_outdoor: bool


@weather_router.get("/weather", response_model=WeatherResponse)
async def get_weather(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
):
    """Lấy thông tin thời tiết hiện tại cho một vị trí.

    Sử dụng Open-Meteo API (free, no API key).
    """
    place_service = get_place_service()
    try:
        result = place_service.get_weather(latitude, longitude)
        return WeatherResponse(**result)
    except PlaceRecommendationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@weather_router.get("/weather/forecast", response_model=ForecastResponse)
async def get_weather_forecast(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
    days: int = Query(default=3, ge=1, le=7, description="Number of days (1-7)"),
):
    """Lấy dự báo thời tiết cho một vị trí.

    Sử dụng Open-Meteo API (free, no API key).
    """
    place_service = get_place_service()
    try:
        result = place_service.get_forecast(latitude, longitude, days)
        return ForecastResponse(**result)
    except PlaceRecommendationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@weather_router.get("/assessments/{assessment_id}/recommendations/weather", response_model=WeatherAdjustmentResponse)
async def get_weather_adjustment(
    assessment_id: str,
    activity_type: str = Query(..., description="Activity type"),
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
    user: dict = Depends(get_current_user),
):
    """Lấy thông tin thời tiết và đề xuất điều chỉnh cho activity.

    Trả về:
    - Thời tiết hiện tại
    - Đánh giá có phù hợp cho hoạt động ngoài trời không
    - Đề xuất thay thế trong nhà nếu thời tiết không tốt
    """
    user_id = user["uid"]

    # Verify ownership
    assessment_repo = get_assessment_repo()
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    place_service = get_place_service()
    try:
        # Get weather
        weather_result = place_service.get_weather(latitude, longitude)

        # Build response
        weather = weather_result.get("weather", {})
        is_good = weather_result.get("is_good_for_outdoor", True)

        adjustment = {
            "status": "good" if is_good else "bad",
            "is_good_for_outdoor": is_good,
        }

        if not is_good:
            adjustment["message"] = weather.get("weather_description", "Thoi tiet khong tot")
            adjustment["suggest_indoor"] = True
        else:
            adjustment["message"] = weather.get("weather_description", "Thoi tiet tot")
            adjustment["suggest_indoor"] = False

        return WeatherAdjustmentResponse(
            activity_code=activity_type,
            weather=weather,
            weather_adjustment=adjustment,
            is_good_for_outdoor=is_good,
        )
    except PlaceRecommendationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
