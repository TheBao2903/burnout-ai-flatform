"""
==============================================================
File: openmeteo_provider.py

OpenMeteoProvider - Giao tiếp với Open-Meteo Weather API.

Open-Meteo là API thời tiết FREE, không cần API key.
Documentation: https://open-meteo.com/en/docs

Responsibilities:
- Lấy thông tin thời tiết hiện tại
- Lấy dự báo thời tiết
- Normalize weather data cho recommendation
- Error handling
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import httpx

from app.modules.recommendation.models.recommendation import WeatherData

logger = logging.getLogger("burnout.openmeteo")


class OpenMeteoError(Exception):
    """Base exception for Open-Meteo errors."""
    pass


class OpenMeteoProvider:
    """Provider cho Open-Meteo Weather API (free, no API key)."""

    BASE_URL = "https://api.open-meteo.com/v1"

    def __init__(self):
        self._timeout = 10  # seconds

    @property
    def is_configured(self) -> bool:
        """Open-Meteo always available (no API key needed)."""
        return True

    def get_current_weather(
        self,
        latitude: float,
        longitude: float,
    ) -> WeatherData:
        """Lấy thời tiết hiện tại.

        Args:
            latitude: User's latitude (-90 to 90)
            longitude: User's longitude (-180 to 180)

        Returns:
            WeatherData object

        Raises:
            OpenMeteoError: If API call fails
        """
        if not -90 <= latitude <= 90:
            raise ValueError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Invalid longitude: {longitude}")

        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": self._get_current_params(),
            "timezone": "auto",
        }

        logger.info(
            "OpenMeteo request: lat=%.4f, lon=%.4f",
            latitude, longitude,
        )

        try:
            response = self._make_request("GET", url, params=params)
            return self._parse_current_weather(response)

        except httpx.TimeoutException:
            logger.error("OpenMeteo timeout")
            raise OpenMeteoError("Weather API timeout")

        except httpx.HTTPStatusError as e:
            logger.error("OpenMeteo HTTP error: %s", e)
            raise OpenMeteoError(f"Weather API error: {e.response.status_code}")

        except Exception as e:
            logger.error("OpenMeteo unexpected error: %s", e)
            raise OpenMeteoError(f"Weather API error: {e}")

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = 3,
    ) -> List[WeatherData]:
        """Lấy dự báo thời tiết.

        Args:
            latitude: User's latitude
            longitude: User's longitude
            days: Số ngày dự báo (1-7)

        Returns:
            List of WeatherData objects
        """
        if not -90 <= latitude <= 90:
            raise ValueError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Invalid longitude: {longitude}")

        days = max(1, min(days, 7))

        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": self._get_daily_params(),
            "forecast_days": days,
            "timezone": "auto",
        }

        try:
            response = self._make_request("GET", url, params=params)
            return self._parse_daily_forecast(response)

        except Exception as e:
            logger.error("OpenMeteo forecast error: %s", e)
            raise OpenMeteoError(f"Weather forecast API error: {e}")

    def get_hourly_forecast(
        self,
        latitude: float,
        longitude: float,
        hours: int = 24,
    ) -> List[WeatherData]:
        """Lấy dự báo theo giờ.

        Args:
            latitude: User's latitude
            longitude: User's longitude
            hours: Số giờ dự báo (1-48)

        Returns:
            List of WeatherData objects
        """
        if not -90 <= latitude <= 90:
            raise ValueError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Invalid longitude: {longitude}")

        hours = max(1, min(hours, 48))

        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": self._get_hourly_params(),
            "forecast_hours": hours,
            "timezone": "auto",
        }

        try:
            response = self._make_request("GET", url, params=params)
            return self._parse_hourly_forecast(response)

        except Exception as e:
            logger.error("OpenMeteo hourly forecast error: %s", e)
            raise OpenMeteoError(f"Weather hourly forecast API error: {e}")

    def _get_current_params(self) -> str:
        """Get current weather parameters."""
        return ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "weather_code",
            "cloud_cover",
            "wind_speed_10m",
            "is_day",
        ])

    def _get_daily_params(self) -> str:
        """Get daily forecast parameters."""
        return ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
        ])

    def _get_hourly_params(self) -> str:
        """Get hourly forecast parameters."""
        return ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "weather_code",
            "cloud_cover",
            "wind_speed_10m",
            "is_day",
        ])

    def _make_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make HTTP request to Open-Meteo."""
        kwargs.setdefault("timeout", self._timeout)

        with httpx.Client() as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

    def _parse_current_weather(self, response: Dict[str, Any]) -> WeatherData:
        """Parse current weather from API response."""
        current = response.get("current", {})
        current_units = response.get("current_units", {})

        # Parse weather code
        weather_code = current.get("weather_code", 0)
        weather_description = self._weather_code_to_description(weather_code)
        is_good_for_outdoor = self._is_good_for_outdoor(weather_code)

        return WeatherData(
            temperature=current.get("temperature_2m"),
            humidity=current.get("relative_humidity_2m"),
            precipitation=current.get("precipitation", 0),
            weather_code=weather_code,
            weather_description=weather_description,
            cloud_cover=current.get("cloud_cover"),
            wind_speed=current.get("wind_speed_10m"),
            is_day=current.get("is_day", 1) == 1,
            is_good_for_outdoor=is_good_for_outdoor,
            uv_index=None,
            sunrise=None,
            sunset=None,
            timezone=response.get("timezone", "UTC"),
            latitude=response.get("latitude"),
            longitude=response.get("longitude"),
            timestamp=datetime.utcnow().isoformat(),
            source="open-meteo",
        )

    def _parse_daily_forecast(self, response: Dict[str, Any]) -> List[WeatherData]:
        """Parse daily forecast from API response."""
        daily = response.get("daily", {})
        dates = daily.get("time", [])
        forecasts = []

        for i, date in enumerate(dates):
            weather_code = daily.get("weather_code", [0])[i] if daily.get("weather_code") else 0
            weather_description = self._weather_code_to_description(weather_code)
            is_good_for_outdoor = self._is_good_for_outdoor(weather_code)

            forecasts.append(WeatherData(
                temperature=daily.get("temperature_2m_max", [None])[i] if daily.get("temperature_2m_max") else None,
                temperature_min=daily.get("temperature_2m_min", [None])[i] if daily.get("temperature_2m_min") else None,
                humidity=None,
                precipitation=daily.get("precipitation_sum", [0])[i] if daily.get("precipitation_sum") else 0,
                precipitation_probability=daily.get("precipitation_probability_max", [0])[i] if daily.get("precipitation_probability_max") else 0,
                weather_code=weather_code,
                weather_description=weather_description,
                cloud_cover=None,
                wind_speed=daily.get("wind_speed_10m_max", [None])[i] if daily.get("wind_speed_10m_max") else None,
                is_day=None,
                is_good_for_outdoor=is_good_for_outdoor,
                uv_index=None,
                sunrise=None,
                sunset=None,
                timezone=response.get("timezone", "UTC"),
                latitude=response.get("latitude"),
                longitude=response.get("longitude"),
                timestamp=date,
                source="open-meteo",
            ))

        return forecasts

    def _parse_hourly_forecast(self, response: Dict[str, Any]) -> List[WeatherData]:
        """Parse hourly forecast from API response."""
        hourly = response.get("hourly", {})
        times = hourly.get("time", [])
        forecasts = []

        for i, time in enumerate(times):
            weather_code = hourly.get("weather_code", [0])[i] if hourly.get("weather_code") else 0
            weather_description = self._weather_code_to_description(weather_code)
            is_good_for_outdoor = self._is_good_for_outdoor(weather_code)

            forecasts.append(WeatherData(
                temperature=hourly.get("temperature_2m", [None])[i] if hourly.get("temperature_2m") else None,
                humidity=hourly.get("relative_humidity_2m", [None])[i] if hourly.get("relative_humidity_2m") else None,
                precipitation=hourly.get("precipitation", [0])[i] if hourly.get("precipitation") else 0,
                weather_code=weather_code,
                weather_description=weather_description,
                cloud_cover=hourly.get("cloud_cover", [None])[i] if hourly.get("cloud_cover") else None,
                wind_speed=hourly.get("wind_speed_10m", [None])[i] if hourly.get("wind_speed_10m") else None,
                is_day=hourly.get("is_day", [1])[i] if hourly.get("is_day") else None,
                is_good_for_outdoor=is_good_for_outdoor,
                uv_index=None,
                sunrise=None,
                sunset=None,
                timezone=response.get("timezone", "UTC"),
                latitude=response.get("latitude"),
                longitude=response.get("longitude"),
                timestamp=time,
                source="open-meteo",
            ))

        return forecasts

    @staticmethod
    def _weather_code_to_description(code: int) -> str:
        """Convert WMO weather code to description.

        WMO Weather interpretation codes (WW):
        https://open-meteo.com/en/docs#weathervariables
        """
        descriptions = {
            0: "Trời quang",
            1: "Hầu hết trời quang",
            2: "Có mây một phần",
            3: "Nhiều mây",
            45: "Sương mù",
            48: "Sương mù đóng băng",
            51: "Mưa phùn nhẹ",
            53: "Mưa phùn vừa",
            55: "Mưa phùn nặng",
            56: "Mưa phùn đóng băng nhẹ",
            57: "Mưa phùn đóng băng nặng",
            61: "Mưa nhẹ",
            63: "Mưa vừa",
            65: "Mưa nặng",
            66: "Mưa đóng băng nhẹ",
            67: "Mưa đóng băng nặng",
            71: "Tuyết nhẹ",
            73: "Tuyết vừa",
            75: "Tuyết nặng",
            77: "Hạt tuyết",
            80: "Mưa rào nhẹ",
            81: "Mưa rào vừa",
            82: "Mưa rào nặng",
            85: "Mưa rào tuyết nhẹ",
            86: "Mưa rào tuyết nặng",
            95: "Dông kèm mưa",
            96: "Dông kèm mưa đá nhẹ",
            99: "Dông kèm mưa đá nặng",
        }
        return descriptions.get(code, f"Thời tiết code {code}")

    @staticmethod
    def _is_good_for_outdoor(weather_code: int) -> bool:
        """Determine if weather is good for outdoor activities.

        Args:
            weather_code: WMO weather code

        Returns:
            True if good for outdoor, False otherwise
        """
        # Bad weather codes
        bad_weather = {
            45, 48,   # Fog
            51, 53, 55, 56, 57,  # Drizzle/freezing drizzle
            61, 63, 65, 66, 67,  # Rain/freezing rain
            71, 73, 75, 77,      # Snow
            80, 81, 82, 85, 86,  # Rain/snow showers
            95, 96, 99,           # Thunderstorm
        }

        if weather_code in bad_weather:
            return False

        # Check for rain
        if 51 <= weather_code <= 67:
            return False

        # Check for snow
        if 71 <= weather_code <= 86:
            return False

        # Check for thunderstorm
        if weather_code >= 95:
            return False

        return True


# ==========================================
# Singleton
# ==========================================

_openmeteo_provider: Optional[OpenMeteoProvider] = None


def get_openmeteo_provider() -> OpenMeteoProvider:
    """Get OpenMeteoProvider singleton."""
    global _openmeteo_provider
    if _openmeteo_provider is None:
        _openmeteo_provider = OpenMeteoProvider()
    return _openmeteo_provider
