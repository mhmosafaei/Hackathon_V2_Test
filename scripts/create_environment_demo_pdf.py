"""Explicit synthetic PDF for offline environmental UI acceptance only."""
from pathlib import Path
import pymupdf

root = Path(__file__).resolve().parents[1]
out = root/'tmp/pdfs'
out.mkdir(parents=True, exist_ok=True)
pdf = pymupdf.open()
for physical_page in range(6):
    page = pdf.new_page()
    lines = ['SYNTHETIC TEST PERMIT - NOT A REAL LICENCE', 'Part 2 - Conditions']
    lines.extend(f'{number}. The operator shall retain work records.' for number in
                 range(physical_page*4+1, min(physical_page*4+5, 23)))
    if physical_page == 0:
        lines.append('Significant wave height shall not exceed 2.5 m during works.')
        lines.append('Synthetic work point: WGS84 latitude 54.1 longitude -6.1.')
    if physical_page == 1:
        lines.append('Disposal is permitted only within Test Zone, radius 0.5 NM.')
    page.insert_text((50,60), '\n\n'.join(lines), fontsize=10)
pdf.save(out/'synthetic-environment-permit.pdf')
pdf[0].get_pixmap().save(out/'synthetic-environment-page1.png')
pdf.close()
print('Created synthetic offline fixture with source-backed wave requirement.')
