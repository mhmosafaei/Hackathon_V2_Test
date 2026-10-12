"""Generic source evidence, independent of whether it is an obligation."""
from enum import StrEnum
from pydantic import Field
from .common import StrictModel

class SourceRecordType(StrEnum):
 CLAUSE='CLAUSE'; TABLE='TABLE'; TABLE_ROW='TABLE_ROW'; SCHEDULE='SCHEDULE'; DEFINITION='DEFINITION'; REFERENCE='REFERENCE'; CONTEXT='CONTEXT'; OTHER='OTHER'
class SourceRecord(StrictModel):
 source_record_id:str
 document_id:str
 record_type:SourceRecordType
 source_text:str
 pages:list[int]=Field(min_length=1)
 section_reference:str|None=None
 table_reference:str|None=None
 row_reference:str|None=None
 column_labels:list[str]=Field(default_factory=list)
 applicability:str|None=None
 parameter:str|None=None
 limit_text:str|None=None
 reference_period:str|None=None
 monitoring_frequency:str|None=None
 compliance_statistic:str|None=None
 operating_mode:str|None=None
 layout_provenance:dict|None=None
 related_record_ids:list[str]=Field(default_factory=list)
 extraction_method:str
 verification_status:str
 ambiguity:list[str]=Field(default_factory=list)
