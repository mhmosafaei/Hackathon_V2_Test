"""Document-agnostic source structure, deliberately separate from executable rules."""
from enum import StrEnum
from pydantic import Field
from .common import StrictModel

class CandidateState(StrEnum):
    STRUCTURALLY_IDENTIFIED='STRUCTURALLY_IDENTIFIED'; OBLIGATION_CANDIDATE='OBLIGATION_CANDIDATE'; INTERPRETATION_REQUIRED='INTERPRETATION_REQUIRED'; EXTERNAL_DOCUMENT_REQUIRED='EXTERNAL_DOCUMENT_REQUIRED'

class SourceSpan(StrictModel):
    page_number:int=Field(ge=1); start:int=Field(ge=0); end:int=Field(ge=0); text:str

class TableCell(StrictModel):
    row:int=Field(ge=0); column:int=Field(ge=0); text:str; header:str|None=None; ambiguous:bool=False

class StructureNode(StrictModel):
    identifier:str; kind:str; title:str|None=None; span:SourceSpan; parent_id:str|None=None; continuation_of:str|None=None; cells:list[TableCell]=Field(default_factory=list)

class ObligationCandidate(StrictModel):
    candidate_id:str; state:CandidateState; source:SourceSpan
    responsible_party:str|None=None; action:str|None=None; trigger:str|None=None; subject:str|None=None
    operator:str|None=None; threshold:float|None=None; unit:str|None=None; time_constraint:str|None=None
    scope:str|None=None; exceptions:str|None=None; required_evidence:list[str]=Field(default_factory=list); consequence:str|None=None
    table_provenance:list[TableCell]=Field(default_factory=list); linked_references:list[str]=Field(default_factory=list); review_required:bool=True; quote_verified:bool=False
