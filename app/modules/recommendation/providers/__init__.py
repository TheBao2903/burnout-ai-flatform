"""Recommendation providers."""
from app.modules.recommendation.providers.overpass_provider import (
    OverpassProvider,
    OverpassError,
    get_overpass_provider,
)
from app.modules.recommendation.providers.openmeteo_provider import (
    OpenMeteoProvider,
    OpenMeteoError,
    get_openmeteo_provider,
)
from app.modules.recommendation.providers.geoapify_provider import (
    GeoapifyProvider,
    GeoapifyError,
    get_geoapify_provider,
)

__all__ = [
    # Overpass (OpenStreetMap)
    "OverpassProvider",
    "OverpassError",
    "get_overpass_provider",
    # OpenMeteo
    "OpenMeteoProvider",
    "OpenMeteoError",
    "get_openmeteo_provider",
    # Geoapify
    "GeoapifyProvider",
    "GeoapifyError",
    "get_geoapify_provider",
]
