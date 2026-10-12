"""Evidence requirements are classified, never simulated or fetched in Stage 1."""
from src.mapping.capability_registry import derive_automation_status
from src.models.common import SourceRole, SourceType
from src.models.environmental import SourceBinding

def classify(variable: str | None, condition_type: str, evidence: list[str]) -> tuple[SourceBinding, object]:
    words = " ".join(evidence).casefold()
    if variable in {"suspended_particulate_matter", "dissolved_oxygen"} or "real time" in words:
        source = SourceType.LOCAL_SENSOR
    elif "ais" in words or "vessel tracking" in words: source = SourceType.AIS_GNSS
    elif "approval" in words or condition_type == "DOCUMENT_APPROVAL": source = SourceType.AUTHORITY_APPROVAL
    elif condition_type in {"CALENDAR_RESTRICTION", "TIME_WINDOW"}: source = SourceType.CALENDAR
    else: source = SourceType.UNKNOWN
    status = derive_automation_status(variable=variable, required_source=source, has_deciding_adapter=source == SourceType.CALENDAR)
    return SourceBinding(source_type=source, role=SourceRole.PRIMARY_COMPLIANCE, deciding=source == SourceType.CALENDAR), status
