"""Create a clearly synthetic six-page, 22-condition PDF for offline UI testing."""
from pathlib import Path
import pymupdf

root = Path(__file__).resolve().parents[1]
target = root / 'tmp' / 'synthetic-marine-permit.pdf'
target.parent.mkdir(exist_ok=True)
document = pymupdf.open()
for number in range(6):
    page = document.new_page()
    text = 'SYNTHETIC TEST PERMIT - NOT A REAL LICENCE\n\n'
    if number == 0:
        text += 'Part 2 - Conditions\nExample Harbour / Example Marine Authority\n\n'
    for condition in range(number * 4 + 1, min(number * 4 + 5, 23)):
        text += f'{condition}. The operator shall retain work records and notify the authority.\nWithin 24 hours submit the incident notification.\n\n'
    if number == 5:
        text += 'Appendix A: synthetic map reference. No actual operating location is supplied.\n'
    page.insert_textbox((50, 50, 545, 790), text, fontsize=11)
document.save(target)
document.close()
print(target)
