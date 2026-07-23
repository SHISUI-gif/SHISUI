"""天気予報取得(src/research/weather_client.py)を検証する。

実際のOpen-Meteo APIには接続せず、requests.getをモック化する。
"""
from src.research import weather_client


def _fake_response(json_body: dict):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return json_body

    return _Resp()


_FORECAST_BODY = {
    "current": {
        "temperature_2m": 24.5,
        "relative_humidity_2m": 80,
        "weather_code": 61,
        "wind_speed_10m": 12.0,
    },
    "daily": {
        "time": ["2026-07-05", "2026-07-06", "2026-07-07"],
        "weather_code": [61, 2, 95],
        "temperature_2m_max": [25.0, 26.0, 24.0],
        "temperature_2m_min": [21.0, 20.0, 19.0],
        "precipitation_probability_max": [80, 30, 60],
    },
}


def test_get_forecast_parses_current_and_daily(monkeypatch):
    monkeypatch.setattr(
        weather_client.requests, "get", lambda url, params, timeout: _fake_response(_FORECAST_BODY)
    )

    report = weather_client.WeatherClient().get_forecast(35.6762, 139.6503, "東京")

    assert report.location_name == "東京"
    assert report.current_temperature == 24.5
    assert report.current_humidity == 80
    assert report.current_weather == "小雨"
    assert len(report.daily_forecasts) == 3
    assert report.daily_forecasts[0].precipitation_probability == 80


def test_weather_code_mapping_falls_back_for_unknown_code(monkeypatch):
    body = {
        "current": {
            "temperature_2m": 20.0,
            "relative_humidity_2m": 50,
            "weather_code": 9999,
            "wind_speed_10m": 5.0,
        },
        "daily": {
            "time": ["2026-07-05"],
            "weather_code": [9999],
            "temperature_2m_max": [21.0],
            "temperature_2m_min": [19.0],
            "precipitation_probability_max": [0],
        },
    }
    monkeypatch.setattr(weather_client.requests, "get", lambda url, params, timeout: _fake_response(body))

    report = weather_client.WeatherClient().get_forecast(35.0, 139.0, "テスト地点")

    assert "不明な天気コード" in report.current_weather


def test_geocode_returns_none_when_no_results(monkeypatch):
    monkeypatch.setattr(
        weather_client.requests, "get", lambda url, params, timeout: _fake_response({"results": []})
    )

    assert weather_client.WeatherClient().geocode("存在しない地名") is None


def test_geocode_returns_coordinates_when_found(monkeypatch):
    monkeypatch.setattr(
        weather_client.requests,
        "get",
        lambda url, params, timeout: _fake_response(
            {"results": [{"latitude": 34.6937, "longitude": 135.5023, "name": "大阪"}]}
        ),
    )

    result = weather_client.WeatherClient().geocode("大阪")

    assert result == (34.6937, 135.5023, "大阪")


def test_get_forecast_for_location_falls_back_to_default_when_geocode_fails(monkeypatch):
    monkeypatch.setattr(
        weather_client, "settings", type(
            "S", (), {
                "weather_default_latitude": 35.6762,
                "weather_default_longitude": 139.6503,
                "weather_default_location_name": "東京",
            }
        )()
    )

    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params))
        if "geocoding" in url:
            return _fake_response({"results": []})
        return _fake_response(_FORECAST_BODY)

    monkeypatch.setattr(weather_client.requests, "get", fake_get)

    report = weather_client.WeatherClient().get_forecast_for_location(location_name="存在しない地名")

    assert report.location_name == "東京"


def test_get_forecast_for_location_uses_default_when_no_location_given(monkeypatch):
    monkeypatch.setattr(
        weather_client, "settings", type(
            "S", (), {
                "weather_default_latitude": 35.6762,
                "weather_default_longitude": 139.6503,
                "weather_default_location_name": "東京",
            }
        )()
    )
    monkeypatch.setattr(weather_client.requests, "get", lambda url, params, timeout: _fake_response(_FORECAST_BODY))

    report = weather_client.WeatherClient().get_forecast_for_location()

    assert report.location_name == "東京"


def test_format_weather_for_llm_includes_current_and_forecast():
    report = weather_client.WeatherReport(
        location_name="東京",
        current_temperature=24.5,
        current_humidity=80,
        current_weather="小雨",
        current_wind_speed_kmh=12.0,
        daily_forecasts=[
            weather_client.DailyForecast(
                date="2026-07-05",
                weather="小雨",
                temperature_max=25.0,
                temperature_min=21.0,
                precipitation_probability=80,
            )
        ],
    )

    formatted = weather_client.format_weather_for_llm(report)

    assert "東京" in formatted
    assert "24.5" in formatted
    assert "80%" in formatted
