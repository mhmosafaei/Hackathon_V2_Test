"""Shared fetch limits; independent of reference-evidence recency policies."""
import json
import math
from pathlib import Path
from .sampling import MARINE_STEPS

ENVIRONMENTAL_MAX_FETCH_HOURS = json.loads(
    (Path(__file__).resolve().parents[2]/'config/environmental_limits.json').read_text()
)['max_fetch_hours']
# Native 15-minute currents need 289 points over 72h. Include outward query
# boundaries without silently truncating an otherwise complete native series.
MAX_EVIDENCE_POINTS = math.ceil(ENVIRONMENTAL_MAX_FETCH_HOURS*3600/min(MARINE_STEPS.values())) + 2
