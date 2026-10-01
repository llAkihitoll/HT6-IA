from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sqlite3

import pytest
from shared import bookings
from shared.open_meteo_client import WeatherProviderError
from shared.weather_contracts import WeatherReading


@pytest.fixture
def tomorrow():
    return (datetime.now(ZoneInfo('America/Guatemala')).date() + timedelta(days=1)).isoformat()


@pytest.fixture
def ideal(monkeypatch):
    monkeypatch.setattr(bookings, 'fetch_weather_reading', lambda _: WeatherReading(10, 20, 0, 10, 24))


def test_persists_and_deduplicates_across_calls(tmp_path, tomorrow, ideal):
    db = tmp_path / 'reservas.sqlite3'
    first = bookings.create_booking(tomorrow, 'Ana Pérez', db_path=db)
    again = bookings.create_booking(tomorrow, '  ANA   Pérez  ', db_path=db)
    assert first['estado'] == 'confirmada'
    assert again['ya_existia'] and first['id'] == again['id']
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM bookings').fetchone()[0] == 1


def test_parallel_retries_are_idempotent(tmp_path, tomorrow, ideal):
    db = tmp_path / 'reservas.sqlite3'
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: bookings.create_booking(tomorrow, 'Ana', db_path=db), range(8)))
    assert len({r['id'] for r in results}) == 1


@pytest.mark.parametrize('reading', [WeatherReading(29, 20, 0, 10, 24),
    WeatherReading(10, 36, 0, 10, 24), WeatherReading(10, 20, .1, 10, 24),
    WeatherReading(10, 20, 0, 76, 24)])
def test_rejects_each_forbidden_condition_even_on_direct_call(monkeypatch, tmp_path, tomorrow, reading):
    monkeypatch.setattr(bookings, 'fetch_weather_reading', lambda _: reading)
    db = tmp_path / 'reservas.sqlite3'
    with pytest.raises(bookings.BookingError, match='No se puede reservar'):
        bookings.create_booking(tomorrow, 'Ana', db_path=db)
    assert not db.exists()


@pytest.mark.parametrize('reading', [WeatherReading(20, 35, 0, 10, 24), WeatherReading(10, 20, 0, 75, 24)])
def test_marginal_is_pending(monkeypatch, tmp_path, tomorrow, reading):
    monkeypatch.setattr(bookings, 'fetch_weather_reading', lambda _: reading)
    result = bookings.create_booking(tomorrow, 'Ana', db_path=tmp_path/'bookings.sqlite3')
    assert result['estado'] == 'pendiente_revision'
    assert result['evaluacion_actual']['status'] == 'marginal'


def test_weather_failure_does_not_write(monkeypatch, tmp_path, tomorrow):
    def fail(_):
        raise WeatherProviderError('Proveedor no disponible')
    monkeypatch.setattr(bookings, 'fetch_weather_reading', fail)
    db = tmp_path / 'bookings.sqlite3'
    with pytest.raises(WeatherProviderError):
        bookings.create_booking(tomorrow, 'Ana', db_path=db)
    assert not db.exists()


def test_retry_rechecks_weather(monkeypatch, tmp_path, tomorrow, ideal):
    db = tmp_path / 'bookings.sqlite3'
    bookings.create_booking(tomorrow, 'Ana', db_path=db)
    monkeypatch.setattr(bookings, 'fetch_weather_reading', lambda _: WeatherReading(40, 20, 0, 10, 24))
    with pytest.raises(bookings.BookingError):
        bookings.create_booking(tomorrow, 'Ana', db_path=db)


@pytest.mark.parametrize('name,hour', [('', '09:00'), ('Ana', '25:00'), ('Ana', '9:00')])
def test_invalid_request_does_not_query_provider(monkeypatch, tmp_path, tomorrow, name, hour):
    def unexpected(_):
        pytest.fail('No debe consultar el clima con datos inválidos')
    monkeypatch.setattr(bookings, 'fetch_weather_reading', unexpected)
    with pytest.raises(bookings.BookingError):
        bookings.create_booking(tomorrow, name, hour, db_path=tmp_path/'b.sqlite3')


def test_out_of_range_rejected_before_network(monkeypatch, tmp_path):
    def unexpected(_):
        pytest.fail('No debe consultar una fecha fuera de rango')
    monkeypatch.setattr(bookings, 'fetch_weather_reading', unexpected)
    far = (datetime.now(ZoneInfo('America/Guatemala')).date() + timedelta(days=16)).isoformat()
    with pytest.raises(WeatherProviderError):
        bookings.create_booking(far, 'Ana', db_path=tmp_path/'b.sqlite3')
