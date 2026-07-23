"""Open-Meteo API(完全無料・APIキー不要)を使った天気予報取得クライアント。

src/research/news_client.pyと同じ考え方(専用SDKは使わず、標準の`requests`で
直接叩く。API側の不調は例外で表面化させ、呼び出し側が静かにスキップできる
ようにする)を踏襲する。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests

from config.settings import settings

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

# WMO Weather interpretation codes(Open-Meteoが採用している気象コード表)
_WEATHER_CODE_JA: dict[int, str] = {
    0: "快晴",
    1: "晴れ",
    2: "薄曇り",
    3: "曇り",
    45: "霧",
    48: "霧氷",
    51: "小雨(霧雨)",
    53: "雨(霧雨)",
    55: "強い雨(霧雨)",
    56: "着氷性の霧雨",
    57: "強い着氷性の霧雨",
    61: "小雨",
    63: "雨",
    65: "強い雨",
    66: "着氷性の雨",
    67: "強い着氷性の雨",
    71: "小雪",
    73: "雪",
    75: "強い雪",
    77: "霧雪",
    80: "にわか雨(弱い)",
    81: "にわか雨",
    82: "激しいにわか雨",
    85: "にわか雪(弱い)",
    86: "激しいにわか雪",
    95: "雷雨",
    96: "雷雨(ひょうを伴う)",
    99: "雷雨(激しいひょうを伴う)",
}


def _describe_weather_code(code: int) -> str:
    return _WEATHER_CODE_JA.get(code, f"不明な天気コード({code})")


@dataclass
class DailyForecast:
    date: str
    weather: str
    temperature_max: float
    temperature_min: float
    precipitation_probability: int


@dataclass
class WeatherReport:
    location_name: str
    current_temperature: float
    current_humidity: int
    current_weather: str
    current_wind_speed_kmh: float
    daily_forecasts: list[DailyForecast] = field(default_factory=list)


class WeatherClient:
    """Open-Meteoのラッパー。APIキー不要。"""

    def geocode(self, location_name: str) -> tuple[float, float, str] | None:
        """地名から緯度経度を引く。見つからなければNone。"""
        response = requests.get(
            _GEOCODING_URL,
            params={"name": location_name, "count": 1, "language": "ja", "format": "json"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json().get("results")
        if not results:
            return None
        top = results[0]
        return top["latitude"], top["longitude"], top.get("name", location_name)

    def get_forecast(
        self, latitude: float, longitude: float, location_name: str, forecast_days: int = 3
    ) -> WeatherReport:
        """指定した緯度経度の現在の天気+今後の予報を取得する。"""
        response = requests.get(
            _FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "Asia/Tokyo",
                "forecast_days": forecast_days,
            },
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()

        current = body["current"]
        daily = body["daily"]
        forecasts = [
            DailyForecast(
                date=daily["time"][i],
                weather=_describe_weather_code(daily["weather_code"][i]),
                temperature_max=daily["temperature_2m_max"][i],
                temperature_min=daily["temperature_2m_min"][i],
                precipitation_probability=daily["precipitation_probability_max"][i],
            )
            for i in range(len(daily["time"]))
        ]

        return WeatherReport(
            location_name=location_name,
            current_temperature=current["temperature_2m"],
            current_humidity=current["relative_humidity_2m"],
            current_weather=_describe_weather_code(current["weather_code"]),
            current_wind_speed_kmh=current["wind_speed_10m"],
            daily_forecasts=forecasts,
        )

    def get_forecast_for_location(
        self, location_name: str | None = None, forecast_days: int = 3
    ) -> WeatherReport:
        """地名(省略可)から天気予報を取得する。地名未指定・ジオコーディング失敗時は
        既定地点(config/settings.pyのWEATHER_DEFAULT_*)にフォールバックする。"""
        if location_name:
            geocoded = self.geocode(location_name)
            if geocoded:
                latitude, longitude, resolved_name = geocoded
                return self.get_forecast(latitude, longitude, resolved_name, forecast_days)

        return self.get_forecast(
            settings.weather_default_latitude,
            settings.weather_default_longitude,
            settings.weather_default_location_name,
            forecast_days,
        )


def format_weather_for_llm(report: WeatherReport) -> str:
    """天気予報を、LLMに読ませるテキスト形式に整形する。"""
    lines = [
        f"{report.location_name}の現在の天気:",
        f"- 天気: {report.current_weather}",
        f"- 気温: {report.current_temperature}°C",
        f"- 湿度: {report.current_humidity}%",
        f"- 風速: {report.current_wind_speed_kmh}km/h",
        "",
        "今後の予報:",
    ]
    for f in report.daily_forecasts:
        lines.append(
            f"- {f.date}: {f.weather}、最高{f.temperature_max}°C/最低{f.temperature_min}°C、"
            f"降水確率{f.precipitation_probability}%"
        )
    return "\n".join(lines)
