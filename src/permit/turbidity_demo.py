"""Explicit, labelled constant-input scenario for the hackathon demo only."""
from datetime import datetime, timezone
import math


def scenario(candidates, check, start, end):
    if check.get('unit') != 'FNU':
        return None
    for candidate in candidates:
        ref = candidate.get('historical_reference') or {}
        value = ref.get('raw_value')
        if (not ref.get('reference_only') or ref.get('qualifies_for_decision') is not False
                or ref.get('unit') != 'FNU' or isinstance(value, bool)
                or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
            continue
        try:
            moment = datetime.fromisoformat(ref['data_time'].replace('Z', '+00:00'))
            request = candidate.get('request') or {}
            a = datetime.fromisoformat(request['start_time'].replace('Z', '+00:00'))
            b = datetime.fromisoformat(request['end_time'].replace('Z', '+00:00'))
            if moment.utcoffset() is None or moment > min(start, datetime.now(timezone.utc)) or not a <= start < end <= b:
                continue
            threshold = float(check['threshold'])
            if not math.isfinite(threshold):
                continue
            triggered = {'>':value > threshold, '>=':value >= threshold, '<':value < threshold,
                '<=':value <= threshold, '=':value == threshold, '==':value == threshold,
                '!=':value != threshold}[check['operator']]
        except (KeyError, ValueError, TypeError):
            continue
        return {'variable':'turbidity', 'value':value, 'unit':'FNU', 'observation_time':ref['data_time'],
            'dataset_id':ref.get('dataset_id'), 'assumed_start':start.isoformat(), 'assumed_end':end.isoformat(),
            'status':'STOP' if triggered else 'WORK', 'demo_only':True,
            'note':f"Planning assumption: historical turbidity {value:.3f} FNU (observed {ref['data_time']}) is assumed constant throughout the planned period. This is not a future forecast. Future turbidity forecasting will be improved."}
    return None
