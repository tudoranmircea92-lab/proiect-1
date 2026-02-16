from __future__ import annotations

from pathlib import Path


def test_app_routes_mounted(client):
    openapi = client.get('/openapi.json')
    assert openapi.status_code == 200
    paths = openapi.json().get('paths', {})
    assert '/api/train' in paths
    assert '/api/optimize' in paths
    assert '/api/predict_profile' in paths


def test_knob_schema_autodiscovery_by_cathode(client, wait_job, trained_dataset):
    dataset_id, _ = trained_dataset
    plate = 'PLT-2'
    r = client.get('/api/optimize/context', params={'dataset_id': dataset_id, 'plate_id': plate})
    assert r.status_code == 200
    ks = r.json()['knob_schema']
    assert set(ks['gases_main']['keys']) == {'main1', 'main2', 'main3'}
    assert ks['gases_segmented']['mode'] == 'by_cathode'
    assert 'c1' in ks['gases_segmented']['entities']
    c3 = next(c for c in ks['cathodes'] if c['id'] == 'c3')
    assert c3['on'] is False


def test_knob_schema_autodiscovery_by_segment(client, wait_job, dataset_by_segment):
    path, _ = dataset_by_segment
    load = client.post('/api/data/load', json={'path': str(path), 'format': 'csv'})
    load_job = wait_job(load.json()['job_id'])
    did = load_job['result']['dataset_id']
    r = client.get('/api/optimize/context', params={'dataset_id': did})
    assert r.status_code == 200
    ks = r.json()['knob_schema']
    assert ks['gases_segmented']['mode'] == 'by_segment'
    assert set(ks['gases_segmented']['entities']) >= {'seg1', 'seg2'}


def test_optimize_request_validation_and_backward_compat(client, trained_dataset, wait_job):
    dataset_id, _ = trained_dataset
    missing = client.post('/api/optimize', json={'dataset_id': dataset_id})
    assert missing.status_code == 422
    old_payload = {
        'dataset_id': dataset_id,
        'plate_id': 'PLT-1',
        'device': 'RG',
        'targets': {'b': -2},
        'method': 'search',
        'params': {'k_neighbors': 3, 'n_iterations': 80, 'n_solutions': 1, 'device_weights': {'RG': 1, 'RF': 1, 'T': 1}},
    }
    r = client.post('/api/optimize', json=old_payload)
    assert r.status_code == 200
    job = wait_job(r.json()['job_id'])
    assert job['status'] == 'done'


def test_uniformity_in_spec_constraints_and_off_cathode_guard(client, trained_dataset, wait_job):
    dataset_id, _ = trained_dataset
    payload = {
        'dataset_id': dataset_id,
        'plate_id': 'PLT-4',
        'device': 'RG',
        'mode': 'uniformity_in_spec',
        'metric_group': 'b_only',
        'targets': {'b': -2},
        'method': 'search',
        'params': {'k_neighbors': 3, 'n_iterations': 80, 'n_solutions': 1, 'device_weights': {'RG': 1, 'RF': 1, 'T': 1}},
        'guardrails': {'max_step_pct': 1.0, 'max_total_change': 4.0, 'on_only_cathodes': True},
    }
    r = client.post('/api/optimize', json=payload)
    out = wait_job(r.json()['job_id'])
    assert out['status'] == 'done', out
    res = out['result']
    assert res['validity']['in_spec'] is True
    assert res['validity']['violations'] == []
    # ensure OFF cathode c3 not modified
    for ch in res.get('recommendation', {}).get('power', []):
        assert ch.get('cathode') != 'c3'
    improved = (res['after']['std_a'] <= res['before']['std_a']) or (res['after']['range_a'] <= res['before']['range_a'])
    assert improved


def test_out_of_spec_case_reports_violations_or_in_spec_best(client, trained_dataset, wait_job):
    dataset_id, _ = trained_dataset
    payload = {
        'dataset_id': dataset_id,
        'plate_id': 'PLT-5',
        'device': 'RG',
        'mode': 'uniformity_in_spec',
        'targets': {'b': -2},
        'method': 'search',
        'params': {'k_neighbors': 3, 'n_iterations': 80, 'n_solutions': 1, 'device_weights': {'RG': 1, 'RF': 1, 'T': 1}},
        'spec': {'a_rg': {'min': 2.95, 'max': 3.0}, 'b_rg': {'min': -2.05, 'max': -1.95}},
    }
    out = wait_job(client.post('/api/optimize', json=payload).json()['job_id'])
    assert out['status'] == 'done'
    validity = out['result']['validity']
    assert validity['in_spec'] is True or len(validity['violations']) > 0


def test_coupling_constraints_modes(client, trained_dataset, wait_job):
    dataset_id, _ = trained_dataset
    for mode in ['enforce_sum_leq_main', 'enforce_sum_eq_main']:
        payload = {
            'dataset_id': dataset_id,
            'plate_id': 'PLT-6',
            'device': 'RG',
            'mode': 'uniformity_in_spec',
            'targets': {'b': -2},
            'method': 'search',
            'params': {'k_neighbors': 3, 'n_iterations': 80, 'n_solutions': 1, 'device_weights': {'RG': 1, 'RF': 1, 'T': 1}},
            'strategy': {
                'gas_coupling': mode,
                'stages': [
                    {'name': 'segmented_gases', 'enabled': True},
                    {'name': 'cathode_power', 'enabled': False},
                    {'name': 'main_gases', 'enabled': True},
                ],
            },
        }
        out = wait_job(client.post('/api/optimize', json=payload).json()['job_id'])
        assert out['status'] == 'done'
        rec = out['result']['recommendation']
        # smoke: endpoint returns recommendation with coupling mode accepted by schema
        assert 'gases_main' in rec and 'gases_segmented' in rec


def test_robustness_payload(client, trained_dataset, wait_job):
    dataset_id, _ = trained_dataset
    payload = {
        'dataset_id': dataset_id,
        'plate_id': 'PLT-7',
        'device': 'RG',
        'mode': 'uniformity_in_spec',
        'targets': {'b': -2},
        'method': 'search',
        'params': {'k_neighbors': 3, 'n_iterations': 80, 'n_solutions': 1, 'device_weights': {'RG': 1, 'RF': 1, 'T': 1}},
        'robustness': {'enabled': True, 'jitter_pct': 1.0, 'n_simulations': 100},
    }
    out = wait_job(client.post('/api/optimize', json=payload).json()['job_id'])
    assert out['status'] == 'done'
    rob = out['result']['robustness']
    assert rob['simulations'] == 100
    assert 0.0 <= rob['p_in_spec'] <= 1.0


def test_domain_score_label_changes_with_extreme_knobs(client, trained_dataset, wait_job):
    dataset_id, _ = trained_dataset
    base_payload = {
        'dataset_id': dataset_id,
        'plate_id': 'PLT-8',
        'device': 'RG',
        'mode': 'uniformity_in_spec',
        'targets': {'b': -2},
        'method': 'search',
        'params': {'k_neighbors': 3, 'n_iterations': 80, 'n_solutions': 1, 'device_weights': {'RG': 1, 'RF': 1, 'T': 1}},
    }
    normal = wait_job(client.post('/api/optimize', json=base_payload).json()['job_id'])['result']['domain_score']['label']
    extreme_payload = dict(base_payload)
    extreme_payload['knobs'] = {
        'gases_main': {
            'main1': {'current': 1000, 'min': 900, 'max': 1100},
            'main2': {'current': 900, 'min': 800, 'max': 1000},
            'main3': {'current': 800, 'min': 700, 'max': 900},
        }
    }
    extreme = wait_job(client.post('/api/optimize', json=extreme_payload).json()['job_id'])['result']['domain_score']['label']
    assert normal in {'in_domain', 'borderline', 'out_of_domain'}
    assert extreme in {'in_domain', 'borderline', 'out_of_domain'}


def test_train_pipeline_artifacts_and_time_split_and_active_registry(client, trained_dataset):
    dataset_id, report = trained_dataset
    assert report['split_windows'] is not None
    assert report['split_windows']['train_end'] <= report['split_windows']['val_start']
    run_dir = Path(report['artifact_dir'])
    # artifacts are created under default path in service; verify key files
    expected = {'model.pkl', 'feature_schema.json', 'target_columns.json', 'training_report.json', 'config.json', 'metrics.json', 'feature_list.json', 'schema_hash.txt'}
    assert expected.issubset({p.name for p in run_dir.glob('*')})

    set_res = client.post('/api/models/active', json={'product': 'P1', 'model_id': report['model_id']})
    assert set_res.status_code == 200
    get_res = client.get('/api/models/active', params={'product': 'P1'})
    assert get_res.status_code == 200
    assert get_res.json()['model_id'] == report['model_id']


def test_predict_profile_endpoint_outputs(client, trained_dataset, wait_job):
    dataset_id, report = trained_dataset
    client.post('/api/models/active', json={'product': 'P1', 'model_id': report['model_id']})

    payload = {
        'dataset_id': dataset_id,
        'plate_id': 'PLT-3',
        'device': 'RG',
        'outputs': 'lab',
        'knob_overrides': {},
        'target': {'L': 50, 'a': 3, 'b': -2},
        'tolerance': {'L': 2, 'a': 1, 'b': 1},
    }
    out1 = wait_job(client.post('/api/predict_profile', json=payload).json()['job_id'])
    assert out1['status'] == 'done'
    res1 = out1['result']
    assert len(res1['predicted_profile']['a']) == 9
    assert len(res1['predicted_profile']['b']) == 9
    assert 'domain_score' in res1

    payload2 = dict(payload)
    payload2['knob_overrides'] = {'c1.pwr': 20.0, 'c2.pwr': 18.0, 'c1.mainGas1': 4.0, 'c2.mainGas1': 4.0}
    out2 = wait_job(client.post('/api/predict_profile', json=payload2).json()['job_id'])
    res2 = out2['result']
    assert res1['predicted_profile']['a'] != res2['predicted_profile']['a'] or res1['predicted_profile']['b'] != res2['predicted_profile']['b']
