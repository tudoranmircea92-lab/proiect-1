from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.core.constants import is_controllable_column


def calculate_feature_importance(model, X: pd.DataFrame, feature_names: list[str]) -> dict:
    if hasattr(model, 'estimators_') and len(getattr(model, 'estimators_', [])) > 0:
        importances_raw = np.mean(np.vstack([est.feature_importances_ for est in model.estimators_]), axis=0)
    else:
        importances_raw = np.array(getattr(model, 'feature_importances_', np.zeros(len(feature_names))))

    rows = []
    by_compartment: dict[str, float] = {}
    cont = 0.0
    ctx = 0.0

    for feat, imp in zip(feature_names, importances_raw):
        importance = float(max(0.0, imp))
        group = 'controllable' if is_controllable_column(feat) else 'context'
        compartment = feat.split('.', 1)[0] if '.' in feat else 'global'
        rows.append({
            'feature': feat,
            'importance': importance,
            'group': group,
            'compartment': compartment,
        })
        by_compartment[compartment] = by_compartment.get(compartment, 0.0) + importance
        if group == 'controllable':
            cont += importance
        else:
            ctx += importance

    rows.sort(key=lambda x: x['importance'], reverse=True)
    comp_rows = [{'compartment': k, 'importance': float(v)} for k, v in by_compartment.items()]
    comp_rows.sort(key=lambda x: x['importance'], reverse=True)
    total = cont + ctx or 1.0

    return {
        'feature_importances': rows,
        'importance_by_compartment': comp_rows,
        'total_controllable_share': cont / total,
        'total_context_share': ctx / total,
    }
