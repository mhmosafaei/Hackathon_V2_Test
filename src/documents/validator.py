"""Validation, conservative review flags, and overlap deduplication."""
from .quote_verifier import verify_quote
from .pdf_parser import PdfPage
from src.models.extracted_condition import ExtractedCondition

ENUM_MAP={'NOTIFICATION':'REPORTING_DEADLINE','GEOGRAPHIC':'GEOFENCE'}

def recover_conditions(raw_conditions: list[dict], pages: list[PdfPage], trusted_page: int) -> tuple[list[ExtractedCondition], list[dict], list[str]]:
    """Losslessly recover known model-shape failures using trusted page provenance."""
    repaired=[]; audit=[]
    for index,original in enumerate(raw_conditions):
        raw=dict(original); changes=[]
        reported=raw.pop('page_number',None)
        raw['page_number']=trusted_page
        if reported != trusted_page: changes.append({'field':'page_number','model_value':reported,'trusted_value':trusted_page})
        value=raw.get('condition_type')
        if value in ENUM_MAP: raw['condition_type']=ENUM_MAP[value]; changes.append({'field':'condition_type','model_value':value,'mapped_value':raw['condition_type']})
        for field in ('threshold','threshold_upper','duration_hours'):
            value=raw.get(field)
            if value is not None and not isinstance(value,(int,float)):
                raw[field]=None; raw['variable_free_text']=((raw.get('variable_free_text') or '')+f' {field}: {value}').strip(); changes.append({'field':field,'model_value':value,'recovered_as':'variable_free_text'})
        try:
            item=ExtractedCondition.model_validate(raw)
            match=verify_quote(item.source_text,pages,trusted_page)
            item=item.model_copy(update={'quote_verified':match.verified,'quote_verification_detail':match.detail,'review_required':True})
            repaired.append(item); audit.append({'raw_index':index,'disposition':'RECOVERED','changes':changes,'quote_verified':match.verified})
        except Exception as exc: audit.append({'raw_index':index,'disposition':'REJECTED','changes':changes,'error':str(exc)})
    seen=set(); unique=[]
    for item in repaired:
        key=' '.join(item.source_text.casefold().split())
        if key in seen: audit.append({'condition_id':item.condition_id,'disposition':'EXACT_DUPLICATE_REMOVED'}); continue
        seen.add(key); unique.append(item)
    return unique,audit,[x.get('error','') for x in audit if x['disposition']=='REJECTED']

def validate_conditions(raw_conditions: list[dict], pages: list[PdfPage]) -> tuple[list[ExtractedCondition], list[str]]:
    accepted, errors, seen = [], [], set()
    for raw in raw_conditions:
        try:
            item = ExtractedCondition.model_validate(raw)
            key = (" ".join(item.source_text.casefold().split()), item.clause or "")
            if key in seen: continue
            seen.add(key)
            match = verify_quote(item.source_text, pages, item.page_number)
            item = item.model_copy(update={"quote_verified": match.verified, "quote_verification_detail": match.detail,
                "review_required": item.review_required or item.threshold is None or not match.verified})
            accepted.append(item)
        except Exception as exc:
            errors.append(str(exc))
    return accepted, errors
