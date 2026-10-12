"""Single user-facing document-intelligence orchestration entry point."""
from pathlib import Path
from src.permit.upload_flow import analyze_ai_first_upload

def analyze_document(pdf:bytes, filename:str, options:dict|None=None, *, root:Path, request=None)->dict:
 """Upload → map → inventory → candidates → verification → review-ready output.

``request`` is injectable for offline/mocked execution. The normal UI calls
the same workflow without exposing internal stages to the reviewer.
 """
 options=options or {}
 if request is None: return analyze_ai_first_upload(root,filename,pdf)
 return analyze_ai_first_upload(root,filename,pdf,request=request)
