"""
==============================================================
File: place_recommendation_service.py

PlaceRecommendationService - Location-based recommendations.

Responsibilities:
- Search places for activities
- Get weather data (Open-Meteo)
- Adjust recommendations based on weather
- Apply personalization
- Record place interactions
- Handle errors gracefully

Flow:
1. Get activity recommendations for assessment
2. Get current weather (Open-Meteo)
3. Map activity -> Geoapify categories
4. If weather is bad -> suggest indoor alternatives
5. Search places with Geoapify
6. Apply place type personalization
7. Return normalized places + weather info
8. Record interaction
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.modules.recommendation.models.recommendation import (
    PlaceRecommendation,
    PlaceInteraction,
    ActivityPlaceMapping,
    WeatherData,
    WeatherRecommendation,
    ActivityWeatherMapping,
)
from app.modules.recommendation.providers.geoapify_provider import (
    GeoapifyProvider,
    GeoapifyError,
    get_geoapify_provider,
)
from app.modules.recommendation.providers.openmeteo_provider import (
    OpenMeteoProvider,
    OpenMeteoError,
    get_openmeteo_provider,
)
from app.modules.recommendation.repositories.recommendation_repository import (
    get_recommendation_history_repository,
    get_place_interaction_repository,
    get_user_recommendation_profile_repository,
)

logger = logging.getLogger("burnout.place.recommendation")


class PlaceRecommendationError(Exception):
    """Error from place recommendation service."""
    pass


class PlaceRecommendationService:
    """Service cho location-based recommendations với weather integration."""

    def __init__(
        self,
        geoapify_provider: Optional[GeoapifyProvider] = None,
        openmeteo_provider: Optional[OpenMeteoProvider] = None,
    ):
        self._geoapify = geoapify_provider or get_geoapify_provider()
        self._weather = openmeteo_provider or get_openmeteo_provider()
        self._history_repo = get_recommendation_history_repository()
        self._place_interaction_repo = get_place_interaction_repository()
        self._profile_repo = get_user_recommendation_profile_repository()

    def search_places(
        self,
        assessment_id: str,
        user_id: str,
        activity_type: str,
        latitude: float,
        longitude: float,
        radius_meters: Optional[int] = None,
        limit: int = 10,
        lang: str = "vi",
        include_weather: bool = True,
    ) -> Dict[str, Any]:
        """Search places for an activity type.

        Args:
            assessment_id: Assessment ID
            user_id: User ID
            activity_type: Activity code (e.g., "outdoor_walk")
            latitude: User latitude
            longitude: User longitude
            radius_meters: Search radius (100-10000)
            limit: Number of places (1-20)
            lang: Language code
            include_weather: Whether to include weather data

        Returns:
            Dict với places, weather info, và weather-adjusted recommendations

        Raises:
            PlaceRecommendationError: Invalid input or service error
        """
        # 1. Validate inputs
        if not -90 <= latitude <= 90:
            raise PlaceRecommendationError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise PlaceRecommendationError(f"Invalid longitude: {longitude}")

        radius = radius_meters or 5000
        if radius < 100 or radius > 10000:
            raise PlaceRecommendationError("Radius must be between 100 and 10000 meters")

        if limit < 1 or limit > 20:
            raise PlaceRecommendationError("Limit must be between 1 and 20")

        # 2. Get weather data
        weather_data = None
        weather_adjustment = None
        if include_weather:
            try:
                weather_data = self._weather.get_current_weather(latitude, longitude)
                logger.info(
                    "Weather for %.4f, %.4f: %s (good_for_outdoor=%s)",
                    latitude, longitude,
                    weather_data.weather_description,
                    weather_data.is_good_for_outdoor,
                )
            except OpenMeteoError as e:
                logger.warning("Failed to get weather: %s", e)
                # Continue without weather

        # 3. Get weather-adjusted recommendation
        if weather_data:
            weather_adjustment = self._get_weather_adjustment(
                activity_type=activity_type,
                weather=weather_data,
            )

        # 4. Determine categories to search
        categories = self._get_search_categories(activity_type, weather_data)

        if not categories:
            logger.info("Activity %s doesn't require places", activity_type)
            return self._build_response(
                assessment_id=assessment_id,
                user_id=user_id,
                activity_type=activity_type,
                places=[],
                categories=[],
                weather_data=weather_data,
                weather_adjustment=weather_adjustment,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
            )

        # 5. Search with Geoapify API
        try:
            places = self._geoapify.search_places(
                latitude=latitude,
                longitude=longitude,
                categories=categories,
                radius_meters=radius,
                limit=limit,
                lang=lang,
            )
        except GeoapifyError as e:
            logger.error("Geoapify API error: %s", e)
            raise PlaceRecommendationError(f"Place search failed: {e}") from e

        # 6. Apply personalization (filter/boost based on user preferences)
        places = self._apply_place_personalization(user_id, places)

        # 7. Record view interaction
        if places:
            self._record_place_view(
                assessment_id=assessment_id,
                user_id=user_id,
                activity_type=activity_type,
                places=places,
            )

        # 8. Build response
        return self._build_response(
            assessment_id=assessment_id,
            user_id=user_id,
            activity_type=activity_type,
            places=places,
            categories=categories,
            weather_data=weather_data,
            weather_adjustment=weather_adjustment,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
        )

    def get_weather(
        self,
        latitude: float,
        longitude: float,
    ) -> Dict[str, Any]:
        """Get current weather for a location.

        Args:
            latitude: User latitude
            longitude: User longitude

        Returns:
            Weather data dict

        Raises:
            PlaceRecommendationError: If weather API fails
        """
        if not -90 <= latitude <= 90:
            raise PlaceRecommendationError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise PlaceRecommendationError(f"Invalid longitude: {longitude}")

        try:
            weather = self._weather.get_current_weather(latitude, longitude)
            return {
                "latitude": latitude,
                "longitude": longitude,
                "weather": weather.model_dump(),
                "is_good_for_outdoor": weather.is_good_for_outdoor,
            }
        except OpenMeteoError as e:
            logger.error("Weather API error: %s", e)
            raise PlaceRecommendationError(f"Weather fetch failed: {e}")

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = 3,
    ) -> Dict[str, Any]:
        """Get weather forecast.

        Args:
            latitude: User latitude
            longitude: User longitude
            days: Number of days (1-7)

        Returns:
            Forecast data dict
        """
        if not -90 <= latitude <= 90:
            raise PlaceRecommendationError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise PlaceRecommendationError(f"Invalid longitude: {longitude}")

        days = max(1, min(days, 7))

        try:
            forecasts = self._weather.get_forecast(latitude, longitude, days)
            return {
                "latitude": latitude,
                "longitude": longitude,
                "forecasts": [f.model_dump() for f in forecasts],
                "count": len(forecasts),
            }
        except OpenMeteoError as e:
            logger.error("Weather forecast error: %s", e)
            raise PlaceRecommendationError(f"Weather forecast failed: {e}")

    def record_place_interaction(
        self,
        user_id: str,
        assessment_id: str,
        place_id: str,
        activity_type: str,
        action: str,
        place_name: Optional[str] = None,
        rating: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Record user interaction with a place.

        Args:
            user_id: User ID
            assessment_id: Assessment ID
            place_id: Geoapify place ID
            activity_type: Activity code
            action: Interaction action
            place_name: Optional place name
            rating: Optional user rating
            notes: Optional notes

        Returns:
            Interaction ID
        """
        interaction = PlaceInteraction(
            user_id=user_id,
            assessment_id=assessment_id,
            place_id=place_id,
            place_name=place_name,
            activity_type=activity_type,
            action=action,
            rating=rating,
            notes=notes,
            created_at=datetime.utcnow(),
        )
        interaction_id = self._place_interaction_repo.save(interaction)

        # Update place type affinity if applicable
        categories = ActivityPlaceMapping.get_categories(activity_type)
        if categories and action in ("saved", "visited", "reviewed", "dismissed"):
            self._place_interaction_repo.update_place_type_affinity(
                user_id=user_id,
                activity_code=activity_type,
                categories=categories,
                action=action,
            )

        logger.info(
            "Recorded place interaction %s for user %s: %s (%s)",
            interaction_id, user_id, place_id, action,
        )
        return interaction_id

    def _get_weather_adjustment(
        self,
        activity_type: str,
        weather: WeatherData,
    ) -> WeatherRecommendation:
        """Get weather-adjusted recommendation for an activity.

        Args:
            activity_type: Activity code
            weather: Current weather data

        Returns:
            WeatherRecommendation with adjustment info
        """
        adjustment = WeatherRecommendation(
            activity_code=activity_type,
            current_weather=weather,
            suggest_indoor_alternatives=False,
        )

        # Check if weather affects this activity
        if ActivityWeatherMapping.is_indoor_activity(activity_type):
            # Indoor activities are not affected by weather
            adjustment.weather_status = "good"
            adjustment.weather_message = None
            return adjustment

        # Check if weather is bad for outdoor
        if not weather.is_good_for_outdoor:
            adjustment.weather_status = "bad"

            # Build weather message
            if weather.weather_description:
                adjustment.weather_message = (
                    f"Thoi tiet hien tai: {weather.weather_description}. "
                )
            if weather.precipitation and weather.precipitation > 0:
                adjustment.weather_message += f"Mua: {weather.precipitation}mm. "
            if weather.temperature:
                adjustment.weather_message += f"Nhiet do: {weather.temperature}°C. "

            adjustment.weather_message += "Khong phu hop cho hoat dong ngoai troi."

            # Get indoor alternatives
            indoor_alternatives = ActivityWeatherMapping.get_indoor_alternatives(activity_type)
            if indoor_alternatives:
                adjustment.suggest_indoor_alternatives = True
                adjustment.alternative_place_types = indoor_alternatives

                # Generate adjusted recommendation
                adjustment.weather_adjusted_recommendation = self._generate_indoor_alternative(
                    activity_type=activity_type,
                    weather=weather,
                )

            return adjustment

        # Weather is good
        adjustment.weather_status = "good"
        if weather.temperature:
            adjustment.weather_message = (
                f"Thoi tiet tot: {weather.weather_description}, {weather.temperature}°C. "
                "Phu hop cho hoat dong ngoai troi."
            )
        else:
            adjustment.weather_message = f"Thoi tiet: {weather.weather_description}. Tot cho hoat dong ngoai troi."

        return adjustment

    def _generate_indoor_alternative(
        self,
        activity_type: str,
        weather: WeatherData,
    ) -> Dict[str, str]:
        """Generate indoor alternative recommendation.

        Args:
            activity_type: Original activity code
            weather: Current weather

        Returns:
            Alternative recommendation dict
        """
        alternatives = {
            "outdoor_walk": {
                "title": "Tap yoga tai nha 20 phut",
                "description": (
                    "Thay vi di bo ngoai troi, ban co the tap yoga tai nha. "
                    "Yoga giup giam stress va cai thien luong mau den nao."
                ),
            },
            "nature": {
                "title": "Tham quan bo sen hoac vuon hoa",
                "description": (
                    "Ban co the den cac dia diem trong nha gan day nhu "
                    "bao tang, phong tranh, thuy canh, hoac benh vien."
                ),
            },
            "exercise": {
                "title": "Tap the duc trong nha hoac gym",
                "description": (
                    "Thay vi tap ngoai troi, ban co the tap gym, yoga, "
                    "hoac tap the duc tai nha voi video huong dan."
                ),
            },
            "relaxation": {
                "title": "Nghi ngoi tai quan cafe trong nha",
                "description": (
                    "Chon quan cafe trong nha de thu gian, doc sach hoac "
                    "nghe nhac thay vi ngoi cong vien."
                ),
            },
            "meditation": {
                "title": "Thuc hanh thien tai nha",
                "description": (
                    "Ban co the thuc hanh thieng dien tai nha trong phong yen lang. "
                    "Tai lieu: ung dung Headspace hoac Calm."
                ),
            },
        }

        return alternatives.get(
            activity_type,
            {
                "title": "Nghi ngoi trong nha",
                "description": "Nghi ngoi va thu gian tai nha ngay hom nay.",
            },
        )

    def _get_search_categories(
        self,
        activity_type: str,
        weather: Optional[WeatherData],
    ) -> List[str]:
        """Get Geoapify categories for search.

        Args:
            activity_type: Activity code
            weather: Current weather data

        Returns:
            List of Geoapify categories
        """
        # Get original categories
        categories = ActivityPlaceMapping.get_categories(activity_type)

        # If weather is bad and activity is outdoor, add indoor alternatives
        if weather and not weather.is_good_for_outdoor:
            if ActivityWeatherMapping.is_outdoor_activity(activity_type):
                indoor_alts = ActivityWeatherMapping.get_indoor_alternatives(activity_type)
                # Add indoor categories that Geoapify understands
                indoor_categories = {
                    "gym": ["gym", "fitness"],
                    "yoga_studio": ["fitness", "leisure"],
                    "mall": ["commercial", "shopping_mall"],
                    "museum": ["museum", "tourism"],
                    "gallery": ["museum", "tourism"],
                    "aquarium": ["tourism", "leisure"],
                    "indoor_cycling": ["gym", "sport"],
                    "home_workout": [],  # No place needed
                }
                for alt in indoor_alts:
                    if alt in indoor_categories:
                        categories.extend(indoor_categories[alt])

        # Remove duplicates
        return list(dict.fromkeys(categories))

    def _apply_place_personalization(
        self,
        user_id: str,
        places: List[PlaceRecommendation],
    ) -> List[PlaceRecommendation]:
        """Apply user place type preferences to search results.

        Args:
            user_id: User ID
            places: List of places from Geoapify

        Returns:
            Places sorted/filtered by preference
        """
        profile = self._profile_repo.get(user_id)

        if not profile or not places:
            return places

        preferred = profile.get("preferred_place_types", {})
        avoided = profile.get("avoided_place_types", {})

        if not preferred and not avoided:
            return places

        # Score each place
        scored_places = []
        for place in places:
            score = 0.0

            for cat in place.categories:
                if cat in preferred:
                    score += preferred[cat] * 0.3
                if cat in avoided:
                    score -= avoided[cat] * 0.3

            scored_places.append((score, place))

        # Sort by score (descending)
        scored_places.sort(key=lambda x: x[0], reverse=True)

        return [p for _, p in scored_places]

    def _record_place_view(
        self,
        assessment_id: str,
        user_id: str,
        activity_type: str,
        places: List[PlaceRecommendation],
    ) -> None:
        """Record that places were viewed.

        Args:
            assessment_id: Assessment ID
            user_id: User ID
            activity_type: Activity type
            places: Places that were returned
        """
        if not places:
            return

        # Just record the search as a view interaction
        # Only record for the first place (representative)
        first_place = places[0]
        self.record_place_interaction(
            user_id=user_id,
            assessment_id=assessment_id,
            place_id=first_place.place_id,
            activity_type=activity_type,
            action="viewed",
            place_name=first_place.name,
        )

    def _build_response(
        self,
        assessment_id: str,
        user_id: str,
        activity_type: str,
        places: List[PlaceRecommendation],
        categories: List[str],
        weather_data: Optional[WeatherData],
        weather_adjustment: Optional[WeatherRecommendation],
        latitude: float,
        longitude: float,
        radius: int,
    ) -> Dict[str, Any]:
        """Build API response.

        Args:
            All the data to include in response

        Returns:
            Response dict
        """
        response = {
            "assessment_id": assessment_id,
            "user_id": user_id,
            "activity_type": activity_type,
            "search_location": {
                "latitude": latitude,
                "longitude": longitude,
                "radius_meters": radius,
            },
            "places": [p.model_dump() for p in places],
            "count": len(places),
            "searched_at": datetime.utcnow().isoformat(),
        }

        # Add weather info if available
        if weather_data:
            response["weather"] = weather_data.model_dump()

        # Add weather adjustment if applicable
        if weather_adjustment:
            response["weather_adjustment"] = {
                "status": weather_adjustment.weather_status,
                "message": weather_adjustment.weather_message,
                "should_adjust": weather_adjustment.suggest_indoor_alternatives,
            }
            if weather_adjustment.weather_adjusted_recommendation:
                response["weather_adjustment"]["adjusted_recommendation"] = (
                    weather_adjustment.weather_adjusted_recommendation
                )
            if weather_adjustment.alternative_place_types:
                response["weather_adjustment"]["alternative_place_types"] = (
                    weather_adjustment.alternative_place_types
                )

        # Add message based on results
        if places:
            response["message"] = f"Tim thay {len(places)} dia diem"
        else:
            response["message"] = "Khong tim thay dia diem nao gan day"

        return response


# ==========================================
# ==========================================
# Survey Methods
# ==========================================

    def geocode_address(self, address: str) -> Dict[str, Any]:
        """Chuyển địa chỉ text thành tọa độ lat/lon.

        Sử dụng Nominatim (OpenStreetMap) - free, no API key.
        Thử nhiều format địa chỉ để tăng khả năng tìm thấy.

        Args:
            address: Địa chỉ text (VD: "Quận 1, TP.HCM")

        Returns:
            Dict với latitude, longitude, formatted_address, success
        """
        import httpx

        try:
            # Clean address
            clean_address = address.strip()
            if not clean_address:
                return {
                    "latitude": 0,
                    "longitude": 0,
                    "formatted_address": "",
                    "success": False,
                    "message": "Địa chỉ trống",
                }

            # Chuẩn hóa địa chỉ Việt Nam
            normalized = self._normalize_vietnamese_address(clean_address)

            url = "https://nominatim.openstreetmap.org/search"
            headers = {
                "User-Agent": "BurnoutAI/1.0 (burnout-ai-platform)",
            }

            # Thử nhiều cách query
            queries_to_try = [
                # Query gốc đã chuẩn hóa
                {"q": normalized, "format": "json", "limit": 1, "addressdetails": 1, "countrycodes": "vn"},
                # Thử thêm "Vietnam"
                {"q": f"{normalized}, Vietnam", "format": "json", "limit": 1, "addressdetails": 1},
                # Thử địa chỉ gốc
                {"q": clean_address, "format": "json", "limit": 1, "addressdetails": 1, "countrycodes": "vn"},
                # Thử với city, state
                {"q": normalized, "format": "json", "limit": 1, "addressdetails": 1, "viewbox": "102.1,23.0,109.5,10.0"},  # Vietnam bounding box
            ]

            with httpx.Client(timeout=15.0) as client:
                for i, params in enumerate(queries_to_try):
                    try:
                        response = client.get(url, params=params, headers=headers)
                        response.raise_for_status()
                        results = response.json()

                        if results:
                            result = results[0]
                            lat = float(result.get("lat", 0))
                            lon = float(result.get("lon", 0))

                            # Kiểm tra tọa độ có trong Vietnam không (rough check)
                            if 8 <= lat <= 24 and 102 <= lon <= 110:
                                logger.info("Geocode success with query #%d: %s -> (%.4f, %.4f)", i+1, clean_address, lat, lon)
                                return {
                                    "latitude": lat,
                                    "longitude": lon,
                                    "formatted_address": result.get("display_name", clean_address),
                                    "success": True,
                                    "message": "OK",
                                }
                    except Exception as e:
                        logger.debug("Geocode query #%d failed: %s", i+1, e)
                        continue

            # Fallback: thử Google Maps Geocoding (nếu có API key)
            google_result = self._geocode_google_fallback(clean_address)
            if google_result:
                return google_result

            return {
                "latitude": 0,
                "longitude": 0,
                "formatted_address": clean_address,
                "success": False,
                "message": f"Không tìm thấy địa chỉ: {clean_address}",
            }

        except Exception as e:
            logger.error("Geocode error for '%s': %s", address, e)
            return {
                "latitude": 0,
                "longitude": 0,
                "formatted_address": "",
                "success": False,
                "message": f"Lỗi: {str(e)}",
            }

    def _normalize_vietnamese_address(self, address: str) -> str:
        """Chuẩn hóa địa chỉ Việt Nam để tìm kiếm tốt hơn.

        Lưu ý: Từ 1/1/2021, TP.HCM bãi bỏ các quận nội thành,
        chuyển thành 5 thành phố trực thuộc:
        - TP. Thủ Đức (Quận 2, 9, Thủ Đức cũ)
        - TP. Dĩ An (Bình Dương)
        - TP. Thuận An (Bình Dương)
        - TP. 7, TP. 8, TP. Gò Vấp (các quận cũ)
        Tuy nhiên OSM/Google vẫn hỗ trợ cả tên cũ và mới.
        """
        import re

        # Các mapping tên viết tắt -> đầy đủ
        # TP.HCM: vẫn giữ mapping vì OSM hỗ trợ cả 2
        mappings = {
            # Thành phố
            r'\bTP\.?\s*HCM\b': 'Ho Chi Minh City',
            r'\bHCM\b': 'Ho Chi Minh City',
            r'\bTP\.?\s*Hà\s*Nội\b': 'Hanoi',
            r'\bHà\s*Nội\b': 'Hanoi',
            r'\bĐN\b': 'Da Nang',
            r'\bDN\b': 'Da Nang',
            r'\bHải\s*Phòng\b': 'Hai Phong',
            r'\bCần\s*Thơ\b': 'Can Tho',

            # TP.HCM cũ - vẫn giữ vì OSM hiểu được
            # District 1, 3, 5, 10, 11, Phú Nhuận, Bình Thạnh...
            r'\bQ\.?\s*(\d+)\b': r'District \1',

            # Các thành phố mới của TP.HCM (từ 2021)
            r'\bTP\.?\s*Thủ\s*Đức\b': 'Thu Duc City',
            r'\bThủ\s*Đức\b': 'Thu Duc City',
            r'\bTP\.?\s*Dĩ\s*An\b': 'Di An City',
            r'\bDĩ\s*An\b': 'Di An City',
            r'\bTP\.?\s*Thuận\s*An\b': 'Thuan An City',
            r'\bThuận\s*An\b': 'Thuan An City',

            # Phường/Xã/Thị trấn
            r'\bP\.?\s*': 'Ward ',
            r'\bTX\.?\s*': 'Town ',
            r'\bTT\.?\s*': 'Township ',

            # Tỉnh/Bình
            r'\bH.\s*Chí\s*Minh\b': 'Ho Chi Minh',
            r'\bBình\s*Dương\b': 'Binh Duong',
        }

        result = address
        for pattern, replacement in mappings.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Loại bỏ ký tự đặc biệt thừa
        result = re.sub(r'\s+', ' ', result)  # Nhiều space -> 1 space
        result = result.strip(', ')

        return result

    def _geocode_google_fallback(self, address: str) -> Optional[Dict[str, Any]]:
        """Fallback dùng Google Maps Geocoding API nếu có API key."""
        from app.core.settings import get_settings

        settings = get_settings()
        api_key = getattr(settings.geoapify, 'google_api_key', None) or None

        if not api_key:
            return None

        import httpx

        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": f"{address}, Vietnam",
                "key": api_key,
                "region": "vn",
                "language": "vi",
            }

            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            if data.get("results") and len(data["results"]) > 0:
                result = data["results"][0]
                location = result.get("geometry", {}).get("location", {})
                return {
                    "latitude": location.get("lat", 0),
                    "longitude": location.get("lng", 0),
                    "formatted_address": result.get("formatted_address", address),
                    "success": True,
                    "message": "OK (Google)",
                }
        except Exception as e:
            logger.debug("Google geocode fallback failed: %s", e)

        return None

    def search_places_for_survey(
        self,
        user_id: str,
        latitude: float,
        longitude: float,
        stress_level: int,
        radius_meters: int = 3000,
        limit: int = 10,
        address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tìm địa điểm giảm stress cho survey.

        Không cần assessment, chỉ cần tọa độ và stress level.

        Args:
            user_id: User ID
            latitude: Latitude
            longitude: Longitude
            stress_level: Mức độ stress (1-10)
            radius_meters: Bán kính tìm kiếm
            limit: Số lượng địa điểm

        Returns:
            Dict với places list
        """
        # Nếu stress level thấp (1-3), không cần tìm địa điểm đặc biệt
        if stress_level <= 3:
            return {
                "places": [],
                "count": 0,
                "searched_location": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "address": address or f"{latitude}, {longitude}",
                "message": "Tình trạng ổn định! Hãy duy trì lối sống lành mạnh.",
            }

        # Search 3 categories: cafe, restaurant, park
        categories = ["cafe", "restaurant", "park"]

        logger.info(f"Searching places for stress_level={stress_level}, lat={latitude}, lon={longitude}")

        all_places = []

        # Search each category
        for category in categories:
            try:
                places = self._geoapify.search_places(
                    latitude=latitude,
                    longitude=longitude,
                    categories=[category],
                    radius_meters=radius_meters,
                    limit=5,  # 5 places per category = 15 total
                    lang="vi",
                )
                logger.info(f"Found {len(places)} {category} places")
                all_places.extend(places)
            except Exception as e:
                logger.error(f"Failed to search {category}: {e}")
                continue

        # Remove duplicates by place_id
        seen_ids = set()
        unique_places = []
        for place in all_places:
            if place.place_id not in seen_ids:
                seen_ids.add(place.place_id)
                unique_places.append(place)

        # Limit results
        unique_places = unique_places[:limit]

        # Generate reason for recommendation based on stress level and category
        def get_reason(category: str, stress: int) -> str:
            """Tạo lý do đề xuất dựa trên category và stress level."""
            category_reasons = {
                "cafe": {
                    "high": "Cà phê giúp bạn thư giãn, giảm căng thẳng và lấy lại năng lượng.",
                    "medium": "Một ly cà phê nhẹ nhàng giữa ngày giúp cải thiện tâm trạng.",
                    "low": "Thưởng thức cà phê là cách tốt để duy trì sự tỉnh táo.",
                },
                "restaurant": {
                    "high": "Bữa ăn ngon giúp phục hồi năng lượng và giảm stress.",
                    "medium": "Nên ăn uống đầy đủ để duy trì sức khỏe và tinh thần.",
                    "low": "Thưởng thức bữa ăn ngon là cách tự thưởng xứng đáng.",
                },
                "park": {
                    "high": "Không gian xanh giúp giảm cortisol và cải thiện tâm trạng ngay lập tức.",
                    "medium": "Đi bộ trong công viên giúp giảm stress và tăng cường sức khỏe.",
                    "low": "Công viên là nơi lý tưởng để thư giãn và tận hưởng thiên nhiên.",
                },
                "gym": {
                    "high": "Tập thể dục giải phóng endorphins - hormone hạnh phúc tự nhiên.",
                    "medium": "Vận động nhẹ nhàng giúp giảm căng thẳng và cải thiện giấc ngủ.",
                    "low": "Duy trì thói quen tập thể dục giúp sức khỏe tinh thần tốt hơn.",
                },
                "spa": {
                    "high": "Massage và spa giúp thư giãn sâu cơ bắp và giảm stress hiệu quả.",
                    "medium": "Chăm sóc bản thân bằng spa là cách tốt để giảm căng thẳng.",
                    "low": "Spa định kỳ giúp duy trì sự cân bằng và thư giãn.",
                },
                "library": {
                    "high": "Đọc sách giúp tâm trí bình yên và thoát khỏi lo lắng.",
                    "medium": "Một không gian yên tĩnh để đọc sách giúp giảm stress hiệu quả.",
                    "low": "Thư viện là nơi tuyệt vời để thư giãn và mở rộng kiến thức.",
                },
                "yoga": {
                    "high": "Yoga kết hợp hơi thở và thiền định giúp giảm anxiety ngay lập tức.",
                    "medium": "Tập yoga nhẹ nhàng giúp cân bằng cảm xúc và giảm căng thẳng.",
                    "low": "Yoga duy trì sự cân bằng giữa cơ thể và tinh thần.",
                },
            }

            stress_level = "high" if stress >= 7 else "medium" if stress >= 5 else "low"

            # Generic reason if category not found
            generic_reasons = {
                "high": "Địa điểm này phù hợp để giảm stress và phục hồi năng lượng.",
                "medium": "Địa điểm tốt để thư giãn và cải thiện tâm trạng.",
                "low": "Địa điểm thư giãn lành mạnh để duy trì sức khỏe tinh thần.",
            }

            cat_lower = category.lower()
            for key, reasons in category_reasons.items():
                if key in cat_lower:
                    return reasons.get(stress_level, generic_reasons[stress_level])

            return generic_reasons[stress_level]

        # Format response
        formatted_places = []
        for place in unique_places:
            # Get primary category for reason
            primary_category = place.categories[0] if place.categories else "place"
            reason = get_reason(primary_category, stress_level)

            formatted_places.append({
                "place_id": place.place_id,
                "name": place.name,
                "category": primary_category,
                "reason": reason,
                "address": place.formatted_address,
                "distance": place.distance_meters,
                "categories": place.categories,
                "opening_hours": place.opening_hours,
                "phone": place.phone,
                "website": place.website,
                "rating": place.rating,
            })

        return {
            "places": formatted_places,
            "count": len(formatted_places),
            "searched_location": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "address": address or f"{latitude}, {longitude}",
            "message": f"Tìm thấy {len(formatted_places)} địa điểm" if formatted_places else "Không tìm thấy địa điểm nào",
        }


# Singleton
# ==========================================

_place_service: Optional[PlaceRecommendationService] = None


def get_place_recommendation_service() -> PlaceRecommendationService:
    """Get PlaceRecommendationService singleton."""
    global _place_service
    if _place_service is None:
        _place_service = PlaceRecommendationService()
    return _place_service
