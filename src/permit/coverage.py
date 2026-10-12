"""Deterministic source-condition gate: incomplete source coverage is never silent."""
def coverage_gate(inventory: list[dict]) -> tuple[bool, list[dict]]:
    gaps=[x for x in inventory if x['status'] not in {'CAPTURED','REJECTED_RECOVERY'}]
    return not gaps, gaps
