"""
==============================================================
File: recommendation.py

Recommendation Models - Extended for Location-based recommendations.

Models:
- Recommendation: Core recommendation with activity codes
- RecommendationActivity: Activity metadata for place mapping
- RecommendationHistory: Track generated recommendations
- RecommendationInteraction: User feedback on recommendations
- UserRecommendationProfile: Personalization data
- PlaceRecommendation: Normalized place from Geoapify
- PlaceInteraction: User interaction with places
==============================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# Activity Types
# ==========================================

class ActivityType(str):
    """Recommendation activity types for place mapping."""

    # Exercise/Outdoor
    OUTDOOR_WALK = "outdoor_walk"
    NATURE = "nature"
    EXERCISE = "exercise"

    # Relaxation
    RELAXATION = "relaxation"
    MEDITATION = "meditation"

    # Social
    SOCIAL = "social"
    CAFE = "cafe"

    # Work-life balance
    HOBBY = "hobby"
    ENTERTAINMENT = "entertainment"

    # Health
    SLEEP = "sleep"
    PROFESSIONAL_HELP = "professional_help"


# ==========================================
# Recommendation (Extended)
# ==========================================

class Recommendation(BaseModel):
    """Khuyen nghi ca nhan hoa - Extended with activity metadata."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "title": "Di bo ngoai troi 30 phut",
                "description": "Di bo tai cong vien giam stress va cai thien tam trang.",
                "priority": "high",
                "target_factor": "stress",
                "activity_code": "outdoor_walk",
                "place_categories": ["park", "natural"],
                "duration_minutes": 30,
                "location_required": True,
            }
        }
    )

    # Core fields
    title: str = Field(..., description="Tieu de")
    description: str = Field(..., description="Mo ta chi tiet")
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium", description="Muc do uu tien"
    )
    target_factor: Optional[str] = Field(
        default=None, description="Factor: sleep, workload, emotion, stress, behavior"
    )

    # Activity fields (for location recommendation)
    activity_code: Optional[str] = Field(
        default=None,
        description="Activity code for place mapping: outdoor_walk, nature, exercise, etc."
    )
    place_categories: Optional[List[str]] = Field(
        default=None,
        description="Geoapify categories for place search"
    )
    duration_minutes: Optional[int] = Field(
        default=None,
        description="Estimated duration in minutes"
    )
    location_required: bool = Field(
        default=True,
        description="Whether this activity requires a location"
    )

    # Metadata
    reason: Optional[str] = Field(
        default=None,
        description="Why this recommendation is suggested"
    )


# ==========================================
# Recommendation Activity Mapping
# ==========================================

class ActivityPlaceMapping:
    """Mapping from activity codes to OSM amenity types for Overpass API."""

    # OSM amenity types (for Overpass API)
    MAPPING: Dict[str, Dict[str, Any]] = {
        "outdoor_walk": {
            "categories": ["park", "natural", "outdoor"],
            "duration_minutes": 30,
            "location_required": True,
        },
        "nature": {
            "categories": ["natural", "park", "lake"],
            "duration_minutes": 60,
            "location_required": True,
        },
        "exercise": {
            "categories": ["sport", "fitness", "gym"],
            "duration_minutes": 45,
            "location_required": True,
        },
        "relaxation": {
            "categories": ["park", "cafe", "leisure"],
            "duration_minutes": 45,
            "location_required": True,
        },
        "meditation": {
            "categories": ["park", "natural", "temple"],
            "duration_minutes": 20,
            "location_required": True,
        },
        "social": {
            "categories": ["cafe", "restaurant", "bar"],
            "duration_minutes": 60,
            "location_required": True,
        },
        "cafe": {
            "categories": ["cafe", "coffee"],
            "duration_minutes": 45,
            "location_required": True,
        },
        "hobby": {
            "categories": ["leisure", "entertainment", "shop"],
            "duration_minutes": 60,
            "location_required": True,
        },
        "entertainment": {
            "categories": ["entertainment", "cinema", "leisure"],
            "duration_minutes": 120,
            "location_required": True,
        },
        "sleep": {
            "categories": [],
            "duration_minutes": 480,
            "location_required": False,
        },
        "professional_help": {
            "categories": [],
            "duration_minutes": 60,
            "location_required": False,
        },
    }

    @classmethod
    def get_categories(cls, activity_code: str) -> List[str]:
        """Get Geoapify categories for activity."""
        mapping = cls.MAPPING.get(activity_code, {})
        return mapping.get("categories", [])

    @classmethod
    def get_duration(cls, activity_code: str) -> Optional[int]:
        """Get default duration for activity."""
        mapping = cls.MAPPING.get(activity_code, {})
        return mapping.get("duration_minutes")

    @classmethod
    def is_location_required(cls, activity_code: str) -> bool:
        """Check if activity requires a location."""
        mapping = cls.MAPPING.get(activity_code, {})
        return mapping.get("location_required", True)


# ==========================================
# Recommendation History
# ==========================================

class RecommendationHistory(BaseModel):
    """History of generated recommendations for an assessment."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "assessment_id": "asm_abc123",
                "user_id": "user_xyz",
                "burnout_score": 72,
                "risk_level": "high",
                "recommendations": [],
                "validity_hours": 24,
                "created_at": "2024-01-20T10:15:00Z"
            }
        }
    )

    assessment_id: str = Field(..., description="Assessment ID")
    user_id: str = Field(..., description="User ID")

    # Burnout state at time of generation
    burnout_score: float = Field(..., description="Burnout score when generated")
    risk_level: str = Field(..., description="Risk level when generated")

    # Recommendations generated
    recommendations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of Recommendation dicts"
    )

    # Validity
    validity_hours: int = Field(
        default=24,
        description="How long this recommendation is valid (hours)"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


# ==========================================
# Recommendation Interaction
# ==========================================

class RecommendationInteraction(BaseModel):
    """User interaction with recommendations."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "user_xyz",
                "assessment_id": "asm_abc123",
                "recommendation_code": "outdoor_walk",
                "action": "completed",
                "duration_minutes": 35,
                "created_at": "2024-01-20T11:00:00Z"
            }
        }
    )

    user_id: str = Field(..., description="User ID")
    assessment_id: str = Field(..., description="Assessment ID")

    # Which recommendation
    recommendation_code: str = Field(..., description="Activity code")
    recommendation_title: Optional[str] = None

    # Interaction type
    action: Literal[
        "viewed",      # User viewed recommendation
        "clicked",     # User clicked for details
        "saved",       # User saved to favorites
        "dismissed",  # User dismissed/hidden
        "started",     # User started activity
        "completed",   # User completed activity
        "liked",       # User liked
        "disliked",    # User disliked
    ] = Field(..., description="Interaction action")

    # Optional metadata
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None

    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# User Recommendation Profile
# ==========================================

class UserRecommendationProfile(BaseModel):
    """Personalization data for recommendations."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "user_xyz",
                "preferred_activities": {
                    "outdoor_walk": 0.85,
                    "nature": 0.72,
                    "exercise": 0.60
                },
                "avoided_activities": {
                    "professional_help": 0.90,
                    "meditation": 0.40
                },
                "preferred_place_types": {
                    "park": 0.90,
                    "cafe": 0.75
                },
                "avoided_place_types": {
                    "gym": 0.60
                },
                "total_interactions": 15,
                "total_completed": 8,
                "updated_at": "2024-01-20T10:15:00Z"
            }
        }
    )

    user_id: str = Field(..., description="User ID")

    # Activity preferences (affinity score 0-1)
    preferred_activities: Dict[str, float] = Field(
        default_factory=dict,
        description="Activity affinity scores (0-1)"
    )
    avoided_activities: Dict[str, float] = Field(
        default_factory=dict,
        description="Activities user tends to avoid"
    )

    # Place type preferences
    preferred_place_types: Dict[str, float] = Field(
        default_factory=dict,
        description="Place type affinity scores (0-1)"
    )
    avoided_place_types: Dict[str, float] = Field(
        default_factory=dict,
        description="Place types user tends to avoid"
    )

    # Statistics
    total_interactions: int = 0
    total_completed: int = 0
    last_interaction_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# Place Recommendation (from Overpass/OpenStreetMap)
# ==========================================

class PlaceRecommendation(BaseModel):
    """Normalized place recommendation from Overpass API (OpenStreetMap)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "place_id": "osm:12345678",
                "provider": "overpass",
                "name": "Công viên Tao Đàn",
                "categories": ["park"],
                "latitude": 10.7769,
                "longitude": 106.7009,
                "distance_meters": 850,
                "formatted_address": "123 Đường Nguyễn Du, Quận 1, TP.HCM",
                "address": {
                    "street": "123 Đường Nguyễn Du",
                    "city": "TP.HCM",
                    "state": None,
                    "postcode": None,
                    "country": "Vietnam"
                },
                "rating": None,
                "opening_hours": None,
            }
        }
    )

    # Identity
    place_id: str = Field(..., description="Provider-specific place ID (prefixed)")
    provider: str = Field(default="overpass", description="Data provider")

    # Basic info
    name: str = Field(..., description="Place name")
    categories: List[str] = Field(
        default_factory=list,
        description="Place categories"
    )

    # Location
    latitude: float = Field(..., description="Latitude")
    longitude: float = Field(..., description="Longitude")
    distance_meters: Optional[int] = Field(
        default=None,
        description="Distance from user's location"
    )

    # Address
    formatted_address: Optional[str] = None
    address: Optional[Dict[str, Optional[str]]] = Field(
        default=None,
        description="Structured address components"
    )

    # Optional info (from provider, may be null)
    rating: Optional[float] = None
    opening_hours: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None

    # Reason why this place is recommended
    reason: Optional[str] = Field(
        default=None,
        description="Lý do đề xuất địa điểm này"
    )


# ==========================================
# Place Interaction
# ==========================================

class PlaceInteraction(BaseModel):
    """User interaction with place recommendations."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "user_xyz",
                "assessment_id": "asm_abc123",
                "place_id": "geoapify:abc123",
                "activity_type": "outdoor_walk",
                "action": "opened",
                "created_at": "2024-01-20T11:05:00Z"
            }
        }
    )

    user_id: str = Field(..., description="User ID")
    assessment_id: str = Field(..., description="Assessment ID")

    # Place info
    place_id: str = Field(..., description="Provider-specific place ID")
    place_name: Optional[str] = None
    activity_type: str = Field(..., description="Activity code")

    # Interaction type
    action: Literal[
        "viewed",      # Place shown in list
        "clicked",      # User clicked for details
        "saved",       # User saved place
        "opened",      # User opened for directions
        "dismissed",  # User dismissed place
        "visited",     # User visited place
        "reviewed",    # User left review
    ] = Field(..., description="Interaction action")

    # Optional metadata
    rating: Optional[float] = None
    notes: Optional[str] = None

    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# Weather Data (from Open-Meteo)
# ==========================================

class WeatherData(BaseModel):
    """Weather data from Open-Meteo API."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "temperature": 28.5,
                "humidity": 75,
                "precipitation": 0.0,
                "weather_code": 3,
                "weather_description": "Nhieu may",
                "cloud_cover": 80,
                "wind_speed": 12.5,
                "is_day": True,
                "is_good_for_outdoor": True,
                "timestamp": "2024-01-20T10:30:00",
                "source": "open-meteo"
            }
        }
    )

    # Temperature
    temperature: Optional[float] = Field(
        default=None,
        description="Nhiet do hien tai (°C)"
    )
    temperature_min: Optional[float] = Field(
        default=None,
        description="Nhiet do thap nhat trong ngay (°C)"
    )
    temperature_max: Optional[float] = Field(
        default=None,
        description="Nhiet do cao nhat trong ngay (°C)"
    )

    # Humidity
    humidity: Optional[float] = Field(
        default=None,
        description="Do am tuong doi (%)"
    )

    # Precipitation
    precipitation: Optional[float] = Field(
        default=0.0,
        description="Luong mua (mm)"
    )
    precipitation_probability: Optional[int] = Field(
        default=None,
        description="Xac suat mua (%)"
    )

    # Weather
    weather_code: int = Field(
        default=0,
        description="WMO weather code"
    )
    weather_description: Optional[str] = Field(
        default=None,
        description="Mo ta thoi tiet"
    )

    # Cloud & Wind
    cloud_cover: Optional[int] = Field(
        default=None,
        description="Do phu may (%)"
    )
    wind_speed: Optional[float] = Field(
        default=None,
        description="Toc do gio (km/h)"
    )

    # Day/Night
    is_day: Optional[bool] = Field(
        default=None,
        description="True neu la ban ngay"
    )

    # Outdoor suitability
    is_good_for_outdoor: bool = Field(
        default=True,
        description="True neu thoi tiet thich hop cho hoat dong ngoai troi"
    )

    # UV & Sun
    uv_index: Optional[float] = Field(
        default=None,
        description="Chi so UV"
    )
    sunrise: Optional[str] = Field(
        default=None,
        description="Gio mat troi moc"
    )
    sunset: Optional[str] = Field(
        default=None,
        description="Gio mat troi lan"
    )

    # Location & Time
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    timestamp: Optional[str] = None
    source: str = "open-meteo"


# ==========================================
# Weather-adjusted Recommendation
# ==========================================

class WeatherRecommendation(BaseModel):
    """Recommendation adjusted based on weather conditions."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "activity_code": "outdoor_walk",
                "weather_status": "bad",
                "weather_message": "Troi dang mua, khong nen ra ngoai",
                "weather_adjusted_recommendation": {
                    "title": "Tap yoga tai nha 20 phut",
                    "description": "Thay the bang yoga trong nha de giu suc khoe"
                },
                "alternative_place_types": ["gym", "yoga_studio", "indoor_cafe"]
            }
        }
    )

    # Original activity
    activity_code: str = Field(..., description="Activity code goc")

    # Weather status
    weather_status: Literal["good", "bad", "uncertain"] = Field(
        default="uncertain",
        description="Tinh trang thoi tiet cho hoat dong ngoai troi"
    )
    weather_message: Optional[str] = Field(
        default=None,
        description="Tin nhan ve thoi tiet cho user"
    )

    # If weather is bad, suggest alternatives
    weather_adjusted_recommendation: Optional[Dict[str, str]] = Field(
        default=None,
        description="Recommendation thay the phu hop voi thoi tiet"
    )
    alternative_place_types: Optional[List[str]] = Field(
        default=None,
        description="Cac loai dia diem thay the (indoor)"
    )

    # Current weather info
    current_weather: Optional[WeatherData] = None

    # Should we suggest indoor alternatives?
    suggest_indoor_alternatives: bool = Field(
        default=False,
        description="True neu nen goi y dia diem trong nha"
    )


# ==========================================
# Activity Weather Suitability
# ==========================================

class ActivityWeatherMapping:
    """Mapping activities to weather conditions for outdoor suitability."""

    # Activities that REQUIRE outdoor
    OUTDOOR_ACTIVITIES = {
        "outdoor_walk",
        "nature",
        "exercise",
    }

    # Activities that are ALWAYS indoor
    INDOOR_ACTIVITIES = {
        "sleep",
        "professional_help",
        "social",
        "cafe",
        "hobby",
        "entertainment",
    }

    # Activities that can be EITHER
    FLEXIBLE_ACTIVITIES = {
        "relaxation",
        "meditation",
    }

    @classmethod
    def is_outdoor_activity(cls, activity_code: str) -> bool:
        """Check if activity requires outdoor location."""
        return activity_code in cls.OUTDOOR_ACTIVITIES

    @classmethod
    def is_indoor_activity(cls, activity_code: str) -> bool:
        """Check if activity is always indoor."""
        return activity_code in cls.INDOOR_ACTIVITIES

    @classmethod
    def is_flexible_activity(cls, activity_code: str) -> bool:
        """Check if activity can be either indoor or outdoor."""
        return activity_code in cls.FLEXIBLE_ACTIVITIES

    @classmethod
    def get_indoor_alternatives(cls, activity_code: str) -> List[str]:
        """Get indoor alternatives for an outdoor activity."""
        alternatives = {
            "outdoor_walk": ["gym", "indoor_cycling", "mall"],
            "nature": ["museum", "gallery", "aquarium"],
            "exercise": ["gym", "yoga_studio", "home_workout"],
        }
        return alternatives.get(activity_code, [])

    @classmethod
    def should_adjust_for_weather(cls, activity_code: str, weather: "WeatherData") -> bool:
        """Check if we should adjust recommendation for weather."""
        # If activity is always indoor, no need to adjust
        if cls.is_indoor_activity(activity_code):
            return False

        # If weather is bad for outdoor AND activity is outdoor
        if not weather.is_good_for_outdoor and cls.is_outdoor_activity(activity_code):
            return True

        # If weather is uncertain, give flexible activities a chance
        if cls.is_flexible_activity(activity_code) and weather.precipitation_probability:
            return weather.precipitation_probability > 30

        return False
