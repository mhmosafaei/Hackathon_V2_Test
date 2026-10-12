"""Versioned, source-grounded table evidence contract; no semantic inference."""
import re, unicodedata
VERSION='source-evidence-v2'

def normal(value): return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value))).strip()

def inventory(table:dict)->dict:
 cells=[]
 for row in table['rows']:
  for cell in row:
   role='HEADER' if cell['row']==1 and cell['text'] else 'BLANK' if not cell['text'] else 'DATA'
   if cell.get('ambiguous'): role='UNKNOWN'
   cells.append({**cell,'id':f"{table['id']}-r{cell['row']}-c{cell['column']}",'role':role,'contract_version':VERSION})
 return {'contract_version':VERSION,'table_id':table['id'],'page':table['page'],'cells':cells}

def validate(table:dict, proposal:dict)->dict:
 inv=inventory(table); cells={x['id']:x for x in inv['cells']}; results=[]
 for claim in proposal.get('claims',[]):
  refs={kind:claim.get(kind,[]) for kind in ('value_cells','context_cells','header_cells','geometry_basis')}
  cited=[cell_id for ids in refs.values() for cell_id in ids]
  if proposal.get('contract_version')!=VERSION or any(x not in cells for x in cited): results.append({'outcome':'REJECTED_UNSUPPORTED','reason':'unknown cell or version'}); continue
  if any(cells[x]['role']=='HEADER' for x in refs['context_cells']): results.append({'outcome':'REJECTED_UNSUPPORTED','reason':'header used as context'}); continue
  if any(cells[x]['role'] in {'BLANK','UNKNOWN'} for x in refs['context_cells']): results.append({'outcome':'STRUCTURAL_RELATION_UNRESOLVED','reason':'context geometry unresolved'}); continue
  source=' '.join(cells[x]['text'] for x in refs['value_cells'])
  if claim.get('value') and normal(claim['value']) not in normal(source): results.append({'outcome':'REJECTED_UNSUPPORTED','reason':'value absent'}); continue
  results.append({'outcome':'STRUCTURAL_RELATION_VERIFIED','source_text_outcome':'SOURCE_TEXT_VERIFIED'})
 return {'contract_version':VERSION,'results':results}
