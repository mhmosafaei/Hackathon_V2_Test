"""Deterministic contract-clause discovery, review persistence and forecast analysis."""
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from src.documents.pdf_parser import PdfPage
from src.documents.quote_verifier import verify_quote
from src.models.common import Confidence
from src.models.contract_clause import ContractWeatherClause, ContractReviewState, RiskAllocation
from src.environment.dashboard import load_belfast, marine_series, weather_series
from src.environment.synchronization import shared_hourly_grid, advisory_intervals, coverage_percent

VARIABLES={'wave':('significant wave height','wave height','wave'), 'wind_gust':('wind gust','gust'), 'wind_speed':('wind speed','wind'), 'current_speed':('current speed','current'), 'visibility':('visibility',)}
def document_id(content: bytes) -> str: return 'contract-'+hashlib.sha256(content).hexdigest()[:16]
def _sentences(text): return [x.strip() for x in re.split(r'(?<=[.;])\s+|\n+',text) if x.strip()]
def extract_weather_clauses(document: str, pages: list[PdfPage]) -> list[ContractWeatherClause]:
    clauses=[]
    for page in pages:
        for index,text in enumerate(_sentences(page.text),1):
            low=text.casefold(); variable=next((name for name,words in VARIABLES.items() if any(word in low for word in words)),None)
            weather=variable or any(word in low for word in ('weather','standby','downtime','extension of time','weather risk'))
            if not weather: continue
            number=re.search(r'(?:(?:not exceed|less than|below|maximum|greater than)\s*)?(\d+(?:\.\d+)?)\s*(m/s|knots?|km/h|metres?|meters?|m|hours?)\b',low)
            operator='<=' if any(word in low for word in ('not exceed','maximum','below','less than')) else None
            threshold=float(number.group(1)) if number else None; unit=number.group(2) if number else None
            hours=re.search(r'(\d+(?:\.\d+)?)\s*(?:continuous|consecutive)?\s*hours?',low)
            risk=RiskAllocation.CONTRACTOR if 'contractor risk' in low else RiskAllocation.EMPLOYER if 'employer risk' in low else RiskAllocation.SHARED if 'shared risk' in low else RiskAllocation.UNSPECIFIED
            consequence='standby/downtime provision' if any(x in low for x in ('standby','downtime')) else 'extension-of-time provision' if 'extension of time' in low else 'weather-risk allocation' if 'risk' in low else None
            verified=verify_quote(text,pages,page.page_number).verified
            ambiguity=None if (variable and (threshold is not None or consequence)) else 'weather-related clause needs human interpretation; variable, threshold or unit is incomplete'
            clauses.append(ContractWeatherClause(clause_id=f'{page.page_number}.{index}',document_id=document,source_text=text,page_number=page.page_number,environmental_variable=variable,operator=operator,threshold=threshold,unit=unit,continuous_hours=float(hours.group(1)) if hours else None,evidence_requirements=['Forecast evidence for agreed site and reference period'],consequence=consequence,risk_allocation=risk,confidence=Confidence.HIGH if variable and threshold is not None else Confidence.LOW,quote_verified=verified,review_required=not verified or ambiguity is not None,ambiguity=ambiguity))
    return clauses
def contract_dir(root:Path,doc_id:str)->Path: return root/'cache'/'contracts'/doc_id
def save_clauses(root:Path,clauses:list[ContractWeatherClause]):
    path=contract_dir(root,clauses[0].document_id); path.mkdir(parents=True,exist_ok=True); (path/'clauses.json').write_text(json.dumps([x.model_dump(mode='json') for x in clauses],indent=2),encoding='utf-8')
def load_clauses(root:Path,doc_id:str)->list[ContractWeatherClause]: return [ContractWeatherClause.model_validate(x) for x in json.loads((contract_dir(root,doc_id)/'clauses.json').read_text())]
def save_review(root:Path,doc_id:str,clause_id:str,state:ContractReviewState,reviewer:str):
    path=contract_dir(root,doc_id); path.mkdir(parents=True,exist_ok=True); file=path/'review.json'; current=json.loads(file.read_text()) if file.exists() else {}; current[clause_id]={'state':state.value,'reviewer':reviewer,'at':datetime.now(timezone.utc).isoformat()}; file.write_text(json.dumps(current,indent=2)); return current[clause_id]
def reviews(root:Path,doc_id:str)->dict:
    file=contract_dir(root,doc_id)/'review.json'; return json.loads(file.read_text()) if file.exists() else {}
def analyse_confirmed(root:Path,clauses:list[ContractWeatherClause],review:dict)->dict:
    """Forecast suitability only; never decides contractual entitlement or legal liability."""
    active=[c for c in clauses if review.get(c.clause_id,{}).get('state')=='CONFIRMED' and c.quote_verified and c.environmental_variable and c.threshold is not None and c.unit]
    if not active: return {'status':'UNKNOWN','reason':'no confirmed, quote-verified contract thresholds are eligible for forecast analysis','windows':[],'clauses':0}
    environment=load_belfast(root); marine,weather=environment['marine'],environment['weather']; series={}
    mapping={'wave':('waves','VHM0','mean'),'wind_speed':(None,'wind_speed_10m','mean'),'wind_gust':(None,'wind_gusts_10m','max'),'current_speed':('currents','current_speed','max')}
    for clause in active:
        product,variable,method=mapping.get(clause.environmental_variable,(None,None,None))
        if not variable: continue
        times,values,_=marine_series(marine.get(product,{}),variable) if product else weather_series(weather,variable)
        series[clause.clause_id]=(times,values,method)
    if len(series)!=len(active): return {'status':'UNKNOWN','reason':'one or more confirmed clauses have unsupported variables or unavailable forecast coverage','windows':[],'clauses':len(active)}
    grid,aligned=shared_hourly_grid(series); quality={key: bool(values) and (weather.get('cache_fresh',False) if active[i].environmental_variable.startswith('wind') else marine.get('waves' if active[i].environmental_variable=='wave' else 'currents',{}).get('cache_fresh',False)) for i,(key,values) in enumerate(aligned.items())}
    thresholds={c.clause_id:c.threshold for c in active}; minimum=max([int(c.continuous_hours or 1) for c in active],default=1)
    windows=advisory_intervals(grid,aligned,thresholds,quality,minimum) if grid else []
    exposure=[{'clause_id':c.clause_id,'consequence':c.consequence,'risk_allocation':c.risk_allocation.value,'notice':'Human legal/commercial review required; forecast exceedance is not entitlement.'} for c in active if c.consequence]
    return {'status':'FORECAST_ANALYSIS_ONLY','forecast_hours':len(grid),'coverage':{key:coverage_percent(values) for key,values in aligned.items()},'windows':windows,'exposure':exposure,'clauses':len(active),'legal_notice':'NOT LEGAL ADVICE. Forecast windows do not establish liability, payment, downtime entitlement or extension of time.'}
