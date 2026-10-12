"""Deterministic permit structure inventory; never creates extracted conditions."""
import re
from .pdf_parser import PdfPage

CLAUSE=re.compile(r'(?m)^\s*(\d+(?:\.\d+)+)(?=\s|$)')
# Simple marine licences commonly use ``1. ...`` through ``22. ...`` rather
# than the hierarchical notation used by environmental permits.  This is a
# structural pattern only; it is deliberately limited to a detected Conditions
# section so particulars such as ``1. Licensee`` are not mislabelled as terms.
SIMPLE_CLAUSE=re.compile(r'(?m)^\s*(\d{1,3})\.\s+(?=[A-Z])')
NUMBERED_CLAUSE=re.compile(r'(?m)^\s*(\d+(?:\.\d+)+|\d{1,3})\.?\s+(?=[A-Z])')
SCHEDULE=re.compile(r'(?im)^\s*(schedule\s+\d+)\s*[–-]?\s*([^\n]*)')
TABLE=re.compile(r'(?im)^\s*(table\s+s?\d+\.\d+)\s*([^\n]*)')
SPECIAL=re.compile(r'(?m)^\s*((?:IC|PO)\d+)\b')

def inspect_permit_structure(pages:list[PdfPage])->dict:
    """Inventory visible clauses/tables with page provenance; ambiguity stays explicit."""
    conditions_page=next((p.page_number for p in pages if re.search(r'(?im)^\s*(?:part\s*\d+\s*[-–]?\s*)?conditions\s*:?[\s]*$',p.text) and (CLAUSE.search(p.text) or SIMPLE_CLAUSE.search(p.text))),None)
    schedules=[]; clauses=[]; simple_clauses=[]; tables=[]; special=[]
    for page in pages:
        for m in SCHEDULE.finditer(page.text): schedules.append({'id':m.group(1).title(),'title':m.group(2).strip(),'page':page.page_number})
        for m in TABLE.finditer(page.text): tables.append({'id':m.group(1).upper(),'title':m.group(2).strip(),'page':page.page_number})
        # A date such as ``14.11.2022`` can look hierarchical.  Once a
        # Conditions section is known, only inspect its text (and following
        # binding pages), never the Part 1 particulars before the heading.
        clause_segment=page.text
        if conditions_page:
            if page.page_number < conditions_page:
                clause_segment=''
            elif page.page_number == conditions_page:
                heading=re.search(r'(?im)^\s*(?:part\s*\d+\s*[-–]?\s*)?conditions\s*:?[\s]*$',page.text)
                if heading:
                    clause_segment=page.text[heading.end():]
        clause_matches=list(CLAUSE.finditer(clause_segment))
        for index,m in enumerate(clause_matches):
            end=clause_matches[index+1].start() if index+1<len(clause_matches) else len(page.text)
            clauses.append({'id':m.group(1),'page':page.page_number,'source_text':clause_segment[m.start():end].strip(),'is_page_terminal':index == len(clause_matches)-1,
                            'referenced_schedules':re.findall(r'(?i)\bschedule\s+\d+(?:\s+table\s+S\d+\.\d+)?',clause_segment[m.start():end])})
        # Only examine text from the Conditions heading onward.  A generic
        # simple-numbered matcher over the whole document would turn Part 1
        # particulars, dates, and legal notes into apparent permit terms.
        if conditions_page and page.page_number >= conditions_page:
            segment=page.text
            if page.page_number == conditions_page:
                heading=re.search(r'(?im)^\s*(?:part\s*\d+\s*[-–]?\s*)?conditions\s*:?[\s]*$',page.text)
                if heading:
                    segment=page.text[heading.end():]
            for index,m in enumerate(list(SIMPLE_CLAUSE.finditer(segment))):
                matches=list(SIMPLE_CLAUSE.finditer(segment))
                end=matches[index+1].start() if index+1<len(matches) else len(segment)
                source=segment[m.start():end].strip()
                simple_clauses.append({'id':m.group(1),'page':page.page_number,'source_text':source,'is_page_terminal':index == len(matches)-1,
                    'referenced_schedules':re.findall(r'(?i)\bschedule\s+\d+(?:\s+table\s+S\d+\.\d+)?',source)})
        for m in SPECIAL.finditer(page.text): special.append({'id':m.group(1),'page':page.page_number})
    all_clauses=clauses+simple_clauses
    return {'conditions_start_page':conditions_page,'conditions_pages':list(range(conditions_page, next((p.page_number for p in pages if conditions_page and p.page_number>conditions_page and re.search(r'(?im)^\s*(?:notes|schedule\s*1)\b',p.text)),len(pages)+1))) if conditions_page else [],'schedules':schedules,'tables':tables,'hierarchical_clauses':clauses,'simple_clauses':simple_clauses,'numbered_clauses':all_clauses,'schedule_obligation_ids':special,'structure_review_required':conditions_page is None}
