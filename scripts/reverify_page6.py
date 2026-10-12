"""Locally refresh page 6 quote flags after a verifier correction; no API use."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.documents.pdf_parser import parse_pdf
from src.documents.quote_verifier import verify_quote

root = Path(__file__).parents[1]
path = root / "cache/extractions/ml2025054/page_06.json"
data = json.loads(path.read_text(encoding="utf-8"))
pages = parse_pdf(root / "data/permits/ML2025054.pdf").pages
for condition in data["conditions"]:
    match = verify_quote(condition["source_text"], pages, condition["page_number"])
    condition["quote_verified"] = match.verified
    condition["quote_verification_detail"] = match.detail
    if not match.verified:
        condition["review_required"] = True
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(sum(x["quote_verified"] for x in data["conditions"]), sum(not x["quote_verified"] for x in data["conditions"]))
