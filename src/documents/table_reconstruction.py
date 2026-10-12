"""Layout-aware, provenance-first tables. No semantic/legal inference is performed."""
from enum import StrEnum
from pathlib import Path
import pymupdf

class TableStatus(StrEnum):
    VERIFIED_STRUCTURE='VERIFIED_STRUCTURE'; PARTIAL_STRUCTURE='PARTIAL_STRUCTURE'; STRUCTURE_REVIEW_REQUIRED='STRUCTURE_REVIEW_REQUIRED'

def reconstruct_tables(path:Path)->list[dict]:
    """Use PyMuPDF vector-table detection; preserve only detected cells and geometry."""
    results=[]; previous=None
    with pymupdf.open(path) as doc:
        for pageno,page in enumerate(doc,1):
            try: found=page.find_tables()
            except Exception as exc:
                results.append({'page':pageno,'status':TableStatus.STRUCTURE_REVIEW_REQUIRED,'error':type(exc).__name__,'rows':[]}); continue
            for index,table in enumerate(found.tables):
                data=table.extract()
                bbox=tuple(round(v,2) for v in table.bbox)
                headers=[str(x or '').strip() for x in (data[0] if data else [])]
                rows=[]; ambiguous=not headers or any(not h for h in headers)
                for ridx,row in enumerate(data[1:],1):
                    cells=[]
                    for cidx,value in enumerate(row):
                        cell=table.cells[ridx*len(headers)+cidx] if ridx*len(headers)+cidx<len(table.cells) else None
                        cells.append({'row':ridx,'column':cidx,'header':headers[cidx] if cidx<len(headers) else None,'text':str(value or '').strip(),'bbox':tuple(round(v,2) for v in cell) if cell else None,'ambiguous':cell is None})
                    rows.append(cells)
                signature=tuple(headers)
                continuation=previous['id'] if previous and previous['headers']==signature else None
                status=TableStatus.VERIFIED_STRUCTURE if rows and not ambiguous else TableStatus.PARTIAL_STRUCTURE if rows else TableStatus.STRUCTURE_REVIEW_REQUIRED
                item={'id':f'p{pageno}-t{index+1}','page':pageno,'bbox':bbox,'headers':headers,'rows':rows,'status':status,'continuation_of':continuation,'suitable_for_ai_interpretation':status==TableStatus.VERIFIED_STRUCTURE,'ambiguities':['missing or merged header cells'] if ambiguous else []}
                results.append(item); previous=item|{'headers':signature}
    return results
