"""
==============================================================
File: overpass_provider.py

OverpassProvider - Giao tiếp với Overpass API (OpenStreetMap).

Miễn phí, không cần API key.
Dữ liệu từ OpenStreetMap.

Responsibilities:
- Search places by location and amenity types
- Normalize responses
- Error handling
==============================================================
"""

import logging
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from app.modules.recommendation.models.recommendation import PlaceRecommendation

logger = logging.getLogger("burnout.overpass")


class OverpassError(Exception):
    """Base exception for Overpass API errors."""
    pass


class OverpassProvider:
    """Provider cho Overpass API (OpenStreetMap)."""

    # Overpass servers - thử theo thứ tự
    OVERPASS_SERVERS = [
        "https://overpass-api.de/api/interpreter",  # Main server
        "https://overpass.kumi.systems/api/interpreter",  # Backup 1
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",  # Backup 2
    ]

    def __init__(self, api_url: Optional[str] = None, timeout: int = 60):
        self._api_url = api_url or "https://overpass-api.de/api/interpreter"
        self._timeout = timeout
        self._server_index = 0

    @property
    def is_configured(self) -> bool:
        """Overpass luôn configured - không cần key."""
        return True

    def search_places(
        self,
        latitude: float,
        longitude: float,
        categories: Optional[List[str]] = None,
        radius_meters: int = 3000,
        limit: int = 10,
        lang: str = "vi",
    ) -> List[PlaceRecommendation]:
        """Search places near a location using Overpass QL.

        Args:
            latitude: User's latitude (-90 to 90)
            longitude: User's longitude (-180 to 180)
            categories: List of OSM amenity types (e.g., ["cafe", "restaurant", "park"])
            radius_meters: Search radius (default 3000m)
            limit: Number of places (1-50)
            lang: Language code (vi, en)

        Returns:
            List of PlaceRecommendation
        """
        # Validate inputs
        if not -90 <= latitude <= 90:
            raise ValueError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Invalid longitude: {longitude}")

        logger.info(f"Overpass search: lat={latitude}, lon={longitude}, radius={radius_meters}, categories={categories}")

        # Map simplified categories to OSM amenity values
        amenity_map = {
            "park": "park",
            "garden": "park",
            "forest": "park",
            "beach": "beach",
            "lake": "water",
            "cafe": "cafe",
            "coffee": "cafe",
            "restaurant": "restaurant",
            "gym": "gym",
            "fitness": "fitness_centre",
            "yoga": "yoga",
            "spa": "spa",
            "massage": "massage",
            "library": "library",
            "book": "books",
            "cinema": "cinema",
            "theater": "theatre",
            "museum": "museum",
            "supermarket": "supermarket",
            "pharmacy": "pharmacy",
            "hospital": "hospital",
            "bank": "bank",
            "atm": "atm",
        }

        # Normalize categories to amenity tags
        amenity_tags = []
        amenity_query_parts = []

        if categories:
            for cat in categories:
                normalized = amenity_map.get(cat.lower(), cat.lower())
                if normalized not in amenity_tags:
                    amenity_tags.append(normalized)

        # Default amenity tags if none specified
        if not amenity_tags:
            amenity_tags = ["cafe"]

        # Build query for cafe, restaurant, park
        amenity_type = amenity_tags[0].lower() if amenity_tags else "cafe"

        # Map category to OSM tag
        tag_map = {
            "cafe": "amenity=cafe",
            "restaurant": "amenity=restaurant",
            "park": "leisure=park",
        }

        osm_tag = tag_map.get(amenity_type, f"amenity={amenity_type}")
        key, value = osm_tag.split("=")

        # Query format: node["key"="value"](around:radius,lat,lon)
        query = (
            f'[out:json][timeout:20];'
            f'node["{key}"="{value}"](around:{radius_meters},{latitude},{longitude});'
            f'out body;'
        )

        logger.info(
            "Overpass query: categories=%s, lat=%.4f, lon=%.4f, radius=%d",
            amenity_tags, latitude, longitude, radius_meters,
        )
        logger.info(f"Query: {query}")

        try:
            response = self._make_request(query)
            elements = response.get("elements", [])
            logger.info(f"Overpass got {len(elements)} raw results")
            return self._normalize_response(response, latitude, longitude, lang)

        except httpx.TimeoutException:
            logger.error("Overpass timeout")
            raise OverpassError("Overpass API timeout")

        except httpx.ConnectError as e:
            logger.error("Overpass connection error: %s", e)
            raise OverpassError(f"Cannot connect to Overpass API: {e}")

        except Exception as e:
            logger.error("Overpass unexpected error: %s", e)
            raise OverpassError(f"Overpass API error: {e}")

    def _make_request(self, query: str) -> Dict[str, Any]:
        """Make HTTP request to Overpass API."""
        # Overpass cần query trong body với key "data"
        data = {"data": query}
        last_error = None

        for server in self.OVERPASS_SERVERS:
            try:
                logger.info(f"Overpass: trying {server}")
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(server, data=data)
                    logger.info(f"Overpass response status: {response.status_code}")
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"Overpass HTTP error on {server}: {e.response.status_code}")
                last_error = f"HTTP {e.response.status_code}"
                continue
            except httpx.TimeoutException:
                logger.warning(f"Overpass timeout on {server}")
                last_error = "Timeout"
                continue
            except httpx.ConnectError as e:
                logger.warning(f"Overpass connection error on {server}: {e}")
                last_error = str(e)
                continue
            except Exception as e:
                logger.warning(f"Overpass error on {server}: {e}")
                last_error = str(e)
                continue

        raise OverpassError(f"All Overpass servers failed: {last_error}")

    def _normalize_response(
        self,
        response: Dict[str, Any],
        user_lat: float,
        user_lon: float,
        lang: str,
    ) -> List[PlaceRecommendation]:
        """Normalize Overpass response to PlaceRecommendation."""
        results: List[PlaceRecommendation] = []
        elements = response.get("elements", [])

        if not elements:
            logger.info("Overpass returned no results - response keys: %s", list(response.keys()))
            return results

        logger.info(f"Overpass got {len(elements)} raw results")

        # Debug: log first element structure
        if elements:
            logger.info(f"First element keys: %s", list(elements[0].keys()))
            logger.info(f"First element sample: %s", str(elements[0])[:500])

        for item in elements:
            try:
                place = self._normalize_place(item, user_lat, user_lon, lang)
                if place:
                    results.append(place)
            except Exception as e:
                logger.warning("Failed to normalize place: %s", e)
                continue

        logger.info(f"Normalized {len(results)} places from Overpass")
        return results

    def _normalize_place(
        self,
        item: Dict[str, Any],
        user_lat: float,
        user_lon: float,
        lang: str,
    ) -> Optional[PlaceRecommendation]:
        """Normalize single Overpass place item."""
        tags = item.get("tags", {})

        # Skip if no name
        name = tags.get("name")
        if not name:
            # Try alternative name fields
            name = tags.get("name:vi") or tags.get("name:en")
        if not name:
            return None

        # Get coordinates - for ways, use center point
        if item.get("type") == "node":
            lat = item.get("lat", 0)
            lon = item.get("lon", 0)
        else:  # way
            center = item.get("center", {})
            lat = center.get("lat", 0)
            lon = center.get("lon", 0)

        if not lat or not lon:
            return None

        # Calculate distance
        distance = self._haversine_distance(user_lat, user_lon, lat, lon)

        # Build address from tags
        address_parts = []
        if tags.get("addr:street"):
            address_parts.append(tags["addr:street"])
        if tags.get("addr:housenumber"):
            address_parts[0] = f"{tags['addr:housenumber']} {address_parts[0]}" if address_parts else tags["addr:housenumber"]
        if tags.get("addr:city"):
            address_parts.append(tags["addr:city"])
        if tags.get("addr:country"):
            address_parts.append(tags["addr:country"])

        formatted_address = ", ".join(address_parts) if address_parts else None

        # Extract amenity type as category
        amenity = tags.get("amenity", "")
        categories = [amenity] if amenity else []

        # Get contact info
        phone = tags.get("phone") or tags.get("contact:phone")
        website = tags.get("website") or tags.get("contact:website")

        # Opening hours
        opening_hours = tags.get("opening_hours")

        return PlaceRecommendation(
            place_id=f"osm:{item.get('id', '')}",
            provider="overpass",
            name=name,
            categories=categories,
            latitude=lat,
            longitude=lon,
            distance_meters=distance,
            formatted_address=formatted_address,
            address={
                "street": tags.get("addr:street"),
                "city": tags.get("addr:city"),
                "state": tags.get("addr:state"),
                "postcode": tags.get("addr:postcode"),
                "country": tags.get("addr:country"),
            },
            rating=None,
            opening_hours=opening_hours,
            phone=phone,
            website=website,
        )

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> int:
        """Calculate distance between two points in meters using Haversine formula."""
        import math

        R = 6371000  # Earth's radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return int(R * c)


# Singleton instance
_overpass_provider: Optional[OverpassProvider] = None


def get_overpass_provider() -> OverpassProvider:
    """Get singleton OverpassProvider instance."""
    global _overpass_provider
    if _overpass_provider is None:
        _overpass_provider = OverpassProvider()
    return _overpass_provider
