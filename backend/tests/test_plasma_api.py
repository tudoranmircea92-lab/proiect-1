from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_plasma_health_contract():
    res = client.get('/api/plasma/health')
    assert res.status_code == 200
    body = res.json()
    assert body['status'] == 'ok'
    assert body['service'] == 'plasma'
    assert 'version' in body
    assert 'time' in body


def test_plasma_stability_contract():
    payload = {
        'from_ts': '2026-02-09T13:47:00',
        'to_ts': '2026-02-16T13:47:00',
        'active_threshold': 0.0,
        'aggregation': 'mean',
        'group_by': ['device', 'plate'],
        'features': ['c4.pwr', 'c4.cur', 'c4.volt'],
        'filters': {'product': ['PLT XN 4mm'], 'thickness_mm': [4.0]},
    }
    res = client.post('/api/plasma/stability', json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body['window']['from_ts'].startswith('2026-02-09')
    assert body['params']['aggregation'] == 'mean'
    assert isinstance(body['series'], list)


def test_legacy_forward_works():
    payload = {
        'from_ts': '2026-02-09T13:47:00',
        'to_ts': '2026-02-16T13:47:00',
        'active_threshold': 0.0,
        'aggregation': 'mean',
        'group_by': ['device', 'plate'],
        'features': ['c4.pwr'],
        'filters': {'product': [], 'thickness_mm': []},
    }
    res = client.post('/api/plasma_stability', json=payload)
    assert res.status_code == 200
    body = res.json()
    assert 'window' in body and 'score' in body


def test_plasma_stability_accepts_from_to_and_agg_aliases():
    payload = {
        'from': '2026-02-09T14:12:00',
        'to': '2026-02-16T14:12:00',
        'active_threshold': 0.0,
        'agg': 'mean',
        'group_by': ['device', 'plate'],
        'features': ['c4.pwr'],
        'filters': {'product': [], 'thickness_mm': []},
    }
    res = client.post('/api/plasma/stability', json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body['params']['aggregation'] == 'mean'
    assert body['window']['from_ts'].startswith('2026-02-09')
