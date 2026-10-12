"""Merge page-3 and deterministic recovery candidates into the persisted aggregate."""
import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
root=Path(__file__).parents[1]; folder=root/'cache/extractions/ml2025054'
agg=json.loads((folder/'aggregate.json').read_text()); additions=json.loads((folder/'page_03.json').read_text())['conditions']
for r in json.loads((folder/'recovered_conditions.json').read_text()):
    c=r['candidate']; c['automation_status']=r['automation_status']; c['recovery_provenance']=r['provenance']; c['quote_verified']=r['quote_verified']; additions.append(c)
seen={(c['page_number'],' '.join(c['source_text'].casefold().split())) for c in agg['conditions']}; added=[]
for c in additions:
    key=(c['page_number'],' '.join(c['source_text'].casefold().split()))
    if key not in seen: seen.add(key); added.append(c)
agg['conditions']+=added; agg['final_condition_count']=len(agg['conditions']); agg['recovered_conditions_added']=len(added); agg['quote_verified_true']=sum(c['quote_verified'] for c in agg['conditions']); agg['quote_verified_false']=sum(not c['quote_verified'] for c in agg['conditions']); (folder/'aggregate.json').write_text(json.dumps(agg,indent=2),encoding='utf-8'); print(len(added),agg['final_condition_count'])
