"""Flexible AI-discovered candidate; never an executable rule."""
from enum import StrEnum
from pydantic import Field
from .common import StrictModel
class CandidateState(StrEnum):
 EXTRACTED_UNVERIFIED='EXTRACTED_UNVERIFIED'; SOURCE_VERIFIED='SOURCE_VERIFIED'; CONTEXT_UNRESOLVED='CONTEXT_UNRESOLVED'; SOURCE_NOT_FOUND='SOURCE_NOT_FOUND'; CONFLICTING_EVIDENCE='CONFLICTING_EVIDENCE'; HUMAN_REVIEW_REQUIRED='HUMAN_REVIEW_REQUIRED'
class CandidateObligation(StrictModel):
 candidate_id:str; document_id:str; document_type:str; source_quotation:str; page_number:int=Field(ge=1)
 section:str|None=None; obligation:str|None=None; obligation_type:str|None=None; parties:list[str]=Field(default_factory=list); action:str|None=None; subject:str|None=None; trigger:str|None=None; deadline:str|None=None; threshold:float|None=None; operator:str|None=None; unit:str|None=None; operating_mode:str|None=None; scope:str|None=None; exception:str|None=None; evidence:list[str]=Field(default_factory=list); linked_references:list[str]=Field(default_factory=list); ambiguity:list[str]=Field(default_factory=list); confidence:float|None=None; state:CandidateState=CandidateState.EXTRACTED_UNVERIFIED; human_review_required:bool=True
