"""Create a separate labelled fixture; never read or overwrite an original licence."""
import json
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def create(destination):
    fixture = json.loads((ROOT/'tests/fixtures/synthetic_environment_requirements.json').read_text())
    # Reuse the installed PDF dependency; ReportLab is not installed here.
    items = [fixture['label'],
             'Standalone synthetic fixture. No real licence text has been modified. '
             'Every value below is a software-test threshold, not a DAERA regulatory limit.']
    seen = set()
    for item in fixture['conditions']:
        if item['text'] in seen:
            continue
        seen.add(item['text'])
        items.append(f"{item['id']}. {item['text']}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((45,45),'PermitPulse Environmental Evidence Test',fontsize=18)
        remaining = page.insert_textbox(pymupdf.Rect(45,65,550,795),'\n\n'.join(items),fontsize=11)
        if remaining < 0:
            raise ValueError('Synthetic fixture text exceeds page; refusing clipped output')
        pdf.save(destination)
        preview=ROOT/'tmp/pdfs/synthetic-evidence-preview.png'
        preview.parent.mkdir(parents=True,exist_ok=True)
        page.get_pixmap().save(preview)


if __name__ == '__main__':
    create(ROOT/'output/pdf/PermitPulse_UNOFFICIAL_Environmental_Test.pdf')
