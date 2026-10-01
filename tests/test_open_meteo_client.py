"""Pruebas unitarias de la integración reutilizable con Open-Meteo."""

import unittest
from datetime import date
from urllib.parse import parse_qs, urlparse

from shared.open_meteo_client import (
    DAILY_VARIABLES,
    LANDING_LATITUDE,
    LANDING_LONGITUDE,
    WeatherProviderError,
    build_forecast_url,
    fetch_weather_reading,
    parse_daily_forecast,
    validate_forecast_date,
)

REFERENCE_DATE = date(2026, 9, 18)
REQUESTED_DATE = date(2026, 9, 22)


def valid_payload() -> dict:
    return {
        "daily": {
            "time": ["2026-09-22"],
            "temperature_2m_mean": [24.5],
            "precipitation_sum": [0.0],
            "cloud_cover_max": [28.0],
            "wind_speed_10m_max": [18.2],
            "wind_gusts_10m_max": [31.4],
        }
    }


class DateValidationTests(unittest.TestCase):
    def test_accepts_today(self):
        self.assertEqual(
            validate_forecast_date("2026-09-18", today=REFERENCE_DATE),
            REFERENCE_DATE,
        )

    def test_accepts_last_day_of_16_day_window(self):
        self.assertEqual(
            validate_forecast_date("2026-10-03", today=REFERENCE_DATE),
            date(2026, 10, 3),
        )

    def test_rejects_sixteen_days_ahead(self):
        with self.assertRaisesRegex(WeatherProviderError, "hasta 16 días"):
            validate_forecast_date("2026-10-04", today=REFERENCE_DATE)

    def test_rejects_past_date(self):
        with self.assertRaisesRegex(WeatherProviderError, "ya pasó"):
            validate_forecast_date("2026-09-17", today=REFERENCE_DATE)

    def test_rejects_invalid_format(self):
        with self.assertRaisesRegex(WeatherProviderError, "YYYY-MM-DD"):
            validate_forecast_date("22/09/2026", today=REFERENCE_DATE)


class RequestTests(unittest.TestCase):
    def test_url_contains_coordinates_date_units_and_daily_variables(self):
        query = parse_qs(urlparse(build_forecast_url(REQUESTED_DATE)).query)

        self.assertEqual(query["latitude"], [str(LANDING_LATITUDE)])
        self.assertEqual(query["longitude"], [str(LANDING_LONGITUDE)])
        self.assertEqual(query["start_date"], ["2026-09-22"])
        self.assertEqual(query["end_date"], ["2026-09-22"])
        self.assertEqual(query["wind_speed_unit"], ["kmh"])
        self.assertEqual(query["precipitation_unit"], ["mm"])
        self.assertEqual(query["daily"][0].split(","), list(DAILY_VARIABLES))

    def test_fetch_injects_request_and_maps_all_five_values(self):
        calls = []

        def fake_request(url: str, timeout: float) -> dict:
            calls.append((url, timeout))
            return valid_payload()

        reading = fetch_weather_reading(
            "2026-09-22", today=REFERENCE_DATE, request_json=fake_request
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(reading.wind_speed_10m, 18.2)
        self.assertEqual(reading.wind_gust_10m, 31.4)
        self.assertEqual(reading.precipitation, 0.0)
        self.assertEqual(reading.cloud_cover, 28.0)
        self.assertEqual(reading.temperature_2m, 24.5)


class ResponseValidationTests(unittest.TestCase):
    def test_rejects_missing_daily_section(self):
        with self.assertRaisesRegex(WeatherProviderError, "sección daily"):
            parse_daily_forecast({}, REQUESTED_DATE)

    def test_rejects_missing_requested_date(self):
        payload = valid_payload()
        payload["daily"]["time"] = ["2026-09-23"]
        with self.assertRaisesRegex(WeatherProviderError, "no devolvió datos"):
            parse_daily_forecast(payload, REQUESTED_DATE)

    def test_rejects_missing_required_value(self):
        payload = valid_payload()
        payload["daily"]["wind_gusts_10m_max"] = [None]
        with self.assertRaisesRegex(WeatherProviderError, "wind_gusts_10m_max"):
            parse_daily_forecast(payload, REQUESTED_DATE)


if __name__ == "__main__":
    unittest.main()


class InvalidReadingTests(unittest.TestCase):
    def test_nonfinite_or_out_of_range_values_are_rejected(self):
        for field, value in [('wind_speed_10m_max', float('nan')),
                             ('wind_gusts_10m_max', float('inf')),
                             ('precipitation_sum', -1), ('cloud_cover_max', 101),
                             ('temperature_2m_mean', True)]:
            with self.subTest(field=field, value=value):
                payload = valid_payload()
                payload['daily'][field] = [value]
                with self.assertRaises(WeatherProviderError):
                    parse_daily_forecast(payload, REQUESTED_DATE)
