"""Conservative source-to-candidate mapping. It identifies structure; it does not interpret law."""
import re
from .pdf_parser import PdfPage
from src.models.source_structure import CandidateState, ObligationCandidate, SourceSpan, StructureNode, TableCell

REFERENCE=re.compile(r'(?i)\b(?:condition\s+\d+(?:\.\d+)+|schedule\s+\d+(?:\s*,?\s*table\s+s?\d+\.\d+)?|table\s+s?\d+\.\d+|(?:IC|PO)\d+|approved\s+\w+(?:\s+\w+){0,4})')
OBLIGATION=re.compile(r'(?i)\b(?:shall|must|may not|shall not|required to|prohibited)\b')

def _span(page, start, end): return SourceSpan(page_number=page.page_number,start=start,end=end,text=page.text[start:end].strip())

def map_structure(pages:list[PdfPage])->dict:
    nodes=[]; candidates=[]; unresolved=[]; prior_table=None
    for page in pages:
        lines=page.text.splitlines(); offset=0
        for row,line in enumerate(lines):
            start=page.text.find(line,offset); offset=max(start+len(line),offset); clean=line.strip()
            if not clean: continue
            if re.match(r'(?i)^schedule\s+\d+\b',clean): nodes.append(StructureNode(identifier=clean.split()[0]+' '+clean.split()[1],kind='schedule',title=clean,span=_span(page,start,start+len(line))))
            if re.match(r'(?i)^table\s+s?\d+\.\d+\b',clean):
                table_id=re.match(r'(?i)^(table\s+s?\d+\.\d+)',clean).group(1).upper(); nodes.append(StructureNode(identifier=table_id,kind='table',title=clean,span=_span(page,start,start+len(line)),continuation_of=prior_table if prior_table==table_id else None)); prior_table=table_id
            if re.match(r'^\d+(?:\.\d+)+\b',clean): nodes.append(StructureNode(identifier=re.match(r'^\d+(?:\.\d+)+',clean).group(),kind='clause',span=_span(page,start,start+len(line))))
            refs=REFERENCE.findall(clean)
            state=CandidateState.OBLIGATION_CANDIDATE if OBLIGATION.search(clean) else CandidateState.STRUCTURALLY_IDENTIFIED
            if 'approved ' in clean.lower(): state=CandidateState.EXTERNAL_DOCUMENT_REQUIRED
            if state!=CandidateState.STRUCTURALLY_IDENTIFIED:
                candidates.append(ObligationCandidate(candidate_id=f'p{page.page_number}-l{row}',state=state,source=_span(page,start,start+len(line)),linked_references=refs))
            for ref in refs:
                if ref.lower().startswith('approved '): unresolved.append({'reference':ref,'page':page.page_number,'state':CandidateState.EXTERNAL_DOCUMENT_REQUIRED})
    return {'nodes':nodes,'candidates':candidates,'unresolved_references':unresolved}
