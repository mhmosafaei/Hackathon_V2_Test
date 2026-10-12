"""Deterministic source-backed recovery of known Stage 1 gaps; no network/LLM."""
import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from src.documents.pdf_parser import parse_pdf
from src.documents.quote_verifier import verify_quote
from src.models.extracted_condition import ExtractedCondition
from src.permit.classification import classify

ROOT=Path(__file__).parents[1]; OUT=ROOT/'cache/extractions/ml2025054/recovered_conditions.json'
pages=parse_pdf(ROOT/'data/permits/ML2025054.pdf').pages
def span(page, start, end=None):
    text=next(x.text for x in pages if x.page_number==page); a=text.index(start)
    try: b=text.index(end,a) if end else len(text)
    except ValueError: b=len(text)
    return text[a:b].strip()
specs=[
 ('1',3,'1.','2.','REPORTING_DEADLINE','licence commencement',12,'months',[], 'REPORT'),
 ('5',3,'5.','6.','EVENT_TRIGGER','material or method variation',None,None,['licensing authority notification'],'NOTIFY'),
 ('6',3,'6.','7.','TIME_WINDOW','licence validity',None,None,[],'MANUAL_CONFIRMATION'),
 ('7',3,'7.','8.','REPORTING_DEADLINE','contractor appointment',4,'weeks',['Department notification'],'NOTIFY'),
 ('9',3,'9.','', 'STATE_TRANSITION','AIS vessel tracking',None,None,['active AIS or vessel positioning system'],'PROVIDE_EXTERNAL_EVIDENCE'),
 ('10',4,'10.','11.','REPORTING_DEADLINE','UKHO notification',4,'weeks',['UKHO notification'],'NOTIFY'),
 ('17',5,'17.','18.','CALENDAR_RESTRICTION','dredging darkness restriction',None,None,[],'NONE'),
 ('18',5,'18.','19.','DOCUMENT_APPROVAL','at depth samples',6,'weeks',['valid at depth samples','written agreement'],'REQUEST_APPROVAL'),
 ('19',5,'19.','20.','MONITORING_OBLIGATION','monitoring stations',6,'weeks',['Department station-position agreement'],'REQUEST_APPROVAL'),
 ('20_station',5,'20.','Suspended solids shall','MONITORING_OBLIGATION','monitoring station capability',None,None,['real time monitoring','threshold breach reporting'],'PROVIDE_EXTERNAL_EVIDENCE'),
 ('22',5,'22.','23.','OPERATING_METHOD','TBT contaminated sediment',None,None,['sampling programme'],'MANUAL_CONFIRMATION'),
 ('23',5,'23.','Reason', 'EQUIPMENT_STATE','environmental bucket or clam',None,None,['operational equipment confirmation'],'MANUAL_CONFIRMATION'),
]
records=[]
for cid,page,start,end,kind,var,threshold,unit,evidence,action in specs:
    source=span(page,start,end or None)
    raw={'condition_id':f'recovery-{cid}','document_type':'PERMIT','document_id':'ML2025054','source_text':source,'page_number':page,'condition_type':kind,'variable':var,'operator':None,'threshold':threshold,'unit':unit,'evidence_requirements':evidence,'required_action':action,'confidence':'HIGH','review_required':True}
    item=ExtractedCondition.model_validate(raw); match=verify_quote(item.source_text,pages,page); binding,status=classify(item.variable,item.condition_type.value,item.evidence_requirements)
    records.append({'candidate':item.model_dump(mode='json'),'quote_verified':match.verified,'quote_detail':match.detail,'source_binding':binding.model_dump(mode='json'),'automation_status':status.value,'provenance':'deterministic recovery from original PDF; original rejected/missing state retained','confirmed':False})
OUT.write_text(json.dumps(records,indent=2),encoding='utf-8'); print(len(records),sum(x['quote_verified'] for x in records))
