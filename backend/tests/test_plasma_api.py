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


def test_plasma_stability_v2_from_to_aliases():
    payload = {
        'from': '2026-02-09T14:12:00',
        'to': '2026-02-16T14:12:00',
        'agg': 'mean',
        'cathode': 'all',
        'window_preset': '24h',
    }
    res = client.post('/api/plasma/stability_v2', json=payload)
    assert res.status_code == 200
    body = res.json()
    assert 'scores' in body and isinstance(body['scores'], list)
    assert 'series_by_cathode' in body and isinstance(body['series_by_cathode'], dict)


def test_plasma_stability_v2_returns_scores_and_series_mapping():
    payload = {
        'from_ts': '2026-02-09T13:47:00',
        'to_ts': '2026-02-16T13:47:00',
        'aggregation': 'mean',
        'cathode': 'all',
    }
    res = client.post('/api/plasma/stability_v2', json=payload)
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body.get('scores'), list)
    assert isinstance(body.get('series_by_cathode'), dict)


def test_plasma_stability_v2_selected_cathode_returns_only_selected_series():
    payload_all = {
        'from_ts': '2026-02-09T13:47:00',
        'to_ts': '2026-02-16T13:47:00',
        'aggregation': 'mean',
        'cathode': 'all',
    }
    all_res = client.post('/api/plasma/stability_v2', json=payload_all)
    assert all_res.status_code == 200
    all_keys = list((all_res.json().get('series_by_cathode') or {}).keys())
    if not all_keys:
        return

    cath = all_keys[0]
    payload_one = dict(payload_all)
    payload_one['cathode'] = cath
    one_res = client.post('/api/plasma/stability_v2', json=payload_one)
    assert one_res.status_code == 200
    one_keys = list((one_res.json().get('series_by_cathode') or {}).keys())
    assert one_keys == [cath]


def test_plasma_columns_includes_latest_ts_defaults():
    res = client.get('/api/plasma/columns')
    assert res.status_code == 200
    body = res.json()
    assert body.get('defaults', {}).get('latest_ts') is not None
    assert 'min_ts' in body.get('defaults', {})
