"""
==============================================================
File: geoapify_provider.py

GeoapifyProvider - Tìm kiếm địa điểm qua Geoapify Places API v2.

Geoapify là dịch vụ tìm kiếm địa điểm tốt hơn OpenStreetMap/Overpass,
đặc biệt cho khu vực Việt Nam.

API: https://apidocs.geoapify.com/docs/places/
Free tier: 3000 requests/day
==============================================================
"""

import logging
import math
from typing import Any, Dict, List, Optional

import httpx

from app.core.settings import get_settings

logger = logging.getLogger("burnout.geoapify")


class GeoapifyError(Exception):
    """Error from Geoapify API."""
    pass


class GeoapifyProvider:
    """Provider tìm kiếm địa điểm qua Geoapify Places API v2."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Geoapify provider.

        Args:
            api_key: Geoapify API key. Nếu None, đọc từ settings.
        """
        settings = get_settings()
        self._api_key = api_key or settings.geoapify.api_key
        # IMPORTANT: API v2 endpoint
        self._base_url = "https://api.geoapify.com/v2/places"

        if not self._api_key:
            logger.warning("Geoapify API key not configured - place search will fail")

    def search_places(
        self,
        latitude: float,
        longitude: float,
        categories: List[str],
        radius_meters: int = 5000,
        limit: int = 10,
        lang: str = "vi",
    ) -> List[Any]:
        """Search places near a location.

        Args:
            latitude: Latitude (decimal degrees, e.g., 11.373275)
            longitude: Longitude (decimal degrees, e.g., 107.396092)
            categories: List of Geoapify categories (e.g., ["cafe", "restaurant"])
            radius_meters: Search radius in meters
            limit: Max results to return
            lang: Language for results

        Returns:
            List of PlaceRecommendation objects

        Raises:
            GeoapifyError: If API call fails
        """
        if not self._api_key:
            raise GeoapifyError("Geoapify API key not configured")

        # Map categories to Geoapify format
        geoapify_categories = self._map_categories(categories)

        if not geoapify_categories:
            logger.info("No valid Geoapify categories for: %s", categories)
            return []

        # Build URL - API v2 requires 'type' and uses 'categories' as comma-separated
        url = self._base_url
        params = {
            # 'type' is required by API v2
            "type": geoapify_categories[0] if geoapify_categories else "poi",
            # 'categories' can be comma-separated for multiple categories
            "categories": ",".join(geoapify_categories),
            # Filter uses circle:lon,lat,radius (lon FIRST!)
            "filter": f"circle:{longitude},{latitude},{radius_meters}",
            # Bias for proximity sorting (lon FIRST!)
            "bias": f"proximity:{longitude},{latitude}",
            "limit": limit,
            "lang": lang,
            "apiKey": self._api_key,
        }

        logger.info(
            "Geoapify search: lat=%.4f, lon=%.4f, categories=%s -> geoapify=%s, radius=%d",
            latitude, longitude, categories, geoapify_categories, radius_meters,
        )

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)

                # Log response status without exposing API key
                logger.info(
                    "Geoapify request status: %d",
                    response.status_code
                )

                response.raise_for_status()
                data = response.json()

            # Parse response
            return self._parse_response(data, latitude, longitude)

        except httpx.HTTPStatusError as e:
            logger.error("Geoapify HTTP error: %d", e.response.status_code)
            raise GeoapifyError(f"HTTP error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Geoapify request error: %s", type(e).__name__)
            raise GeoapifyError(f"Request error: {e}") from e
        except Exception as e:
            logger.error("Geoapify unexpected error: %s", e)
            raise GeoapifyError(f"Unexpected error: {e}") from e

    def _map_categories(self, categories: List[str]) -> List[str]:
        """Map app categories to Geoapify v2 categories.

        Geoapify v2 categories:
        https://apidocs.geoapify.com/docs/places/

        Args:
            categories: List of app categories

        Returns:
            List of Geoapify category codes
        """
        # Mapping từ app categories -> Geoapify categories
        # Verified against official Geoapify v2 taxonomy
        category_map = {
            # Cafe & Drinks
            "cafe": "catering.cafe",
            "coffee_shop": "catering.cafe",
            "tea_house": "catering.cafe",
            "tea": "catering.cafe",
            # Restaurant
            "restaurant": "catering.restaurant",
            "food_court": "catering.fast_food",
            "fast_food": "catering.fast_food",
            # Parks & Nature - IMPORTANT: correct category is 'leisure.park'
            "park": "leisure.park",
            "nature": "leisure.park",
            "garden": "leisure.park.garden",
            "outdoor": "leisure.park",
            # Entertainment
            "cinema": "entertainment.cinema",
            "theater": "entertainment.theatre",
            "theatre": "entertainment.theatre",
            "museum": "tourism.museum",
            "gallery": "tourism.museum",
            # Sports & Fitness
            "gym": "sport.fitness_centre",
            "fitness": "sport.fitness_centre",
            "fitness_centre": "sport.fitness_centre",
            "yoga": "sport.fitness_centre",
            "yoga_studio": "sport.fitness_centre",
            "swimming": "sport.swimming_pool",
            "sports": "sport",
            # Relaxation
            "spa": "beauty.spa",
            "massage": "beauty.massage",
            "meditation": "leisure.park",  # Meditation spaces often in parks
            # Shopping
            "mall": "building.commercial",
            "shopping": "building.commercial",
            "supermarket": "commercial.supermarket",
            # Study
            "library": "office.library",
            "coworking": "office.coworking_space",
        }

        result = []
        for cat in categories:
            cat_lower = cat.lower().replace("-", "_").replace(" ", "_")
            if cat_lower in category_map:
                result.append(category_map[cat_lower])
            elif cat in category_map:
                result.append(category_map[cat])

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for c in result:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return unique

    def _parse_response(
        self,
        data: Dict[str, Any],
        user_lat: float,
        user_lon: float,
    ) -> List[Any]:
        """Parse Geoapify v2 response to PlaceRecommendation objects.

        Args:
            data: Geoapify API response (FeatureCollection)
            user_lat: User latitude (for distance calculation)
            user_lon: User longitude (for distance calculation)

        Returns:
            List of PlaceRecommendation objects
        """
        from app.modules.recommendation.models.recommendation import PlaceRecommendation

        # Validate response structure
        features = data.get("features")
        if not isinstance(features, list):
            logger.warning("Geoapify response: features is not a list, got %s", type(features))
            return []

        total_features = len(features)
        parsed_count = 0
        failed_count = 0

        places = []
        for feature in features:
            try:
                # Parse each feature
                place = self._parse_feature(feature, user_lat, user_lon)
                if place:
                    places.append(place)
                    parsed_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(
                    "Failed to parse feature: %s (feature has keys: %s)",
                    e, list(feature.keys()) if isinstance(feature, dict) else "N/A"
                )

        logger.info(
            "Geoapify response: total=%d, parsed=%d, failed=%d",
            total_features, parsed_count, failed_count
        )

        return places

    def _parse_feature(
        self,
        feature: Dict[str, Any],
        user_lat: float,
        user_lon: float,
    ) -> Optional[Any]:
        """Parse a single GeoJSON Feature to PlaceRecommendation.

        Args:
            feature: GeoJSON Feature object
            user_lat: User latitude
            user_lon: User longitude

        Returns:
            PlaceRecommendation or None if parse fails
        """
        from app.modules.recommendation.models.recommendation import PlaceRecommendation

        try:
            # Extract properties from feature
            properties = feature.get("properties", {})
            if not isinstance(properties, dict):
                logger.debug("Feature has no properties dict")
                return None

            # Get place name - REQUIRED field
            name = properties.get("name")
            if not name:
                logger.debug("Feature has no name, skipping")
                return None

            # Get coordinates - prefer properties.lat/lon (more reliable)
            lat = properties.get("lat")
            lon = properties.get("lon")

            # Fallback to geometry if properties doesn't have lat/lon
            if lat is None or lon is None:
                geometry = feature.get("geometry", {})
                coords = geometry.get("coordinates", [])
                if len(coords) >= 2:
                    # GeoJSON coordinates are [lon, lat]
                    lon = coords[0]
                    lat = coords[1]

            # Validate coordinates
            if lat is None or lon is None:
                logger.debug("Feature has no valid coordinates for: %s", name)
                return None

            # Validate geographic ranges
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                logger.debug("Invalid coordinates for %s: lat=%.4f, lon=%.4f", name, lat, lon)
                return None

            # Calculate distance if not provided by API
            distance = properties.get("distance")
            if distance is None:
                distance = self._haversine_distance(user_lat, user_lon, lat, lon)

            # Get address
            address = self._extract_address(properties)

            # Get categories
            categories = properties.get("categories", [])
            if not isinstance(categories, list):
                categories = []

            # Get contact info
            phone = properties.get("phone")
            website = properties.get("website")

            # Get opening hours
            opening_hours = properties.get("opening_hours")

            # Get rating - note: Geoapify uses 'rate' field
            rating = properties.get("rate")

            # Get place_id (stable identifier from Geoapify)
            place_id = properties.get("place_id") or f"geoapify_{lon}_{lat}"

            return PlaceRecommendation(
                place_id=place_id,
                name=name,
                categories=categories[:5],  # Limit categories
                latitude=lat,
                longitude=lon,
                formatted_address=address,
                distance_meters=round(distance),
                phone=phone,
                website=website,
                opening_hours=opening_hours,
                rating=rating,
            )

        except Exception as e:
            logger.debug("Exception parsing feature: %s", e)
            return None

    def _extract_address(self, properties: Dict[str, Any]) -> str:
        """Extract formatted address from properties.

        Args:
            properties: Geoapify feature properties

        Returns:
            Formatted address string
        """
        # Prefer 'formatted' field if available
        formatted = properties.get("formatted")
        if formatted:
            return formatted

        # Fallback to building from address components
        parts = []
        for key in ["address_line1", "address_line2"]:
            val = properties.get(key)
            if val:
                parts.append(str(val))

        if parts:
            return ", ".join(parts)

        # Fallback to city + country
        city = properties.get("city", "")
        country = properties.get("country", "")
        if city or country:
            return ", ".join(filter(None, [city, country]))

        return ""

    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate distance between two points in meters using Haversine formula.

        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point

        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


# ==========================================
# Singleton
# ==========================================

_geoapify_provider: Optional[GeoapifyProvider] = None


def get_geoapify_provider() -> GeoapifyProvider:
    """Get GeoapifyProvider singleton."""
    global _geoapify_provider
    if _geoapify_provider is None:
        _geoapify_provider = GeoapifyProvider()
    return _geoapify_provider
