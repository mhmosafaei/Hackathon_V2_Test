import pymupdf
from pathlib import Path
import os
from src.documents.table_reconstruction import reconstruct_tables, TableStatus

def test_vector_table_preserves_headers_cells_and_geometry():
    pdf=Path('table-reconstruction-fixture.pdf'); doc=pymupdf.open(); page=doc.new_page(); shape=page.new_shape()
    for x in (50,150,250): shape.draw_line((x,50),(x,150))
    for y in (50,83,116,150): shape.draw_line((50,y),(250,y))
    shape.finish(color=(0,0,0)); shape.commit()
    for pos,text in [((55,70),'Activity'),((155,70),'Limit'),((55,103),'A1'),((155,103),'95 percentile'),((55,136),'A2'),((155,136),'4 m3/d')]: page.insert_text(pos,text)
    doc.save(pdf)
    try:
        tables=reconstruct_tables(pdf)
        assert len(tables)==1 and tables[0]['status']==TableStatus.VERIFIED_STRUCTURE
        assert tables[0]['headers']==['Activity','Limit']
        assert tables[0]['rows'][1][1]['text']=='4 m3/d' and tables[0]['rows'][1][1]['bbox']
    finally:
        if pdf.exists(): os.remove(pdf)
