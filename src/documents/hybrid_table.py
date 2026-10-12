"""Mock-safe contract for optional multimodal table interpretation."""
from dataclasses import dataclass
import re, unicodedata
from typing import Literal

State=Literal['VERIFIED_STRUCTURE','PARTIAL_STRUCTURE','STRUCTURE_REVIEW_REQUIRED']

@dataclass(frozen=True)
class CellRef:
    row:int; column:int

def interpretation_packet(table:dict, neighbours:int=1)->dict:
    """AI input payload: image is supplied by caller, never fetched or sent here."""
    return {'table_id':table['id'],'page':table['page'],'headers':table['headers'],'bbox':table['bbox'],'rows':table['rows'],'neighbour_rows':neighbours,
            'instruction':'Propose only relationships between listed source cells. Return cell references, alternatives, confidence, and uncertainty; do not infer values.'}

def validate_proposal(table:dict, proposal:dict)->dict:
    """Reject hallucinated cells/values; confidence is not verification."""
    cells={(cell['row'],cell['column']):cell for row in table['rows'] for cell in row}
    errors=[]; verified=[]
    for relation in proposal.get('relationships',[]):
        refs=[tuple(ref) for ref in relation.get('cells',[])]
        if not refs or any(ref not in cells for ref in refs): errors.append({'relation':relation,'reason':'unknown source cell'}); continue
        claimed=relation.get('values',[])
        source=' '.join(cells[ref]['text'] for ref in refs)
        normal=lambda value: re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value))).strip()
        if any(normal(value) not in normal(source) for value in claimed): errors.append({'relation':relation,'reason':'value absent from referenced source cells'}); continue
        if any(cells[ref]['ambiguous'] for ref in refs): errors.append({'relation':relation,'reason':'ambiguous source geometry'}); continue
        verified.append(relation)
    state='VERIFIED_STRUCTURE' if verified and not errors and table.get('status')=='VERIFIED_STRUCTURE' else 'PARTIAL_STRUCTURE' if verified else 'STRUCTURE_REVIEW_REQUIRED'
    return {'state':state,'verified_relationships':verified,'errors':errors,'model_confidence':proposal.get('confidence'),'review_required':state!='VERIFIED_STRUCTURE'}
