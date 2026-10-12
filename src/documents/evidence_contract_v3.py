"""Finite-vocabulary source citation schema; generated only from local inventory."""
from .evidence_contract_v2 import inventory
VERSION='source-evidence-v3'
def allowed_ids(table): return [c['id'] for c in inventory(table)['cells']]
def schema(table):
 ids=allowed_ids(table); ref={'type':'array','items':{'type':'string','enum':ids}}
 claim={'type':'object','additionalProperties':False,'properties':{'value':{'type':'string'},'value_cells':ref,'context_cells':ref,'header_cells':ref,'geometry_basis':ref},'required':['value','value_cells','context_cells','header_cells','geometry_basis']}
 return {'type':'object','additionalProperties':False,'properties':{'contract_version':{'type':'string','const':VERSION},'claims':{'type':'array','items':claim}},'required':['contract_version','claims']}
def classify_v2_reference(table,cell_id):
 return 'IN_INVENTORY' if cell_id in allowed_ids(table) else ('OFF_BY_ONE_OR_FABRICATED' if '-r' in cell_id and '-c' in cell_id else 'MALFORMED')
