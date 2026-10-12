from src.documents.hybrid_table import interpretation_packet, validate_proposal

TABLE={'id':'x','page':1,'bbox':(0,0,1,1),'headers':['Activity','Limit'],'status':'VERIFIED_STRUCTURE','rows':[[{'row':1,'column':0,'text':'A1','ambiguous':False},{'row':1,'column':1,'text':'4 m3/d','ambiguous':False}]]}
def test_mock_proposal_requires_existing_cells_and_source_values():
 assert interpretation_packet(TABLE)['table_id']=='x'
 good=validate_proposal(TABLE,{'confidence':.99,'relationships':[{'cells':[[1,0],[1,1]],'values':['A1','4 m3/d']} ]})
 assert good['state']=='VERIFIED_STRUCTURE'
 bad=validate_proposal(TABLE,{'relationships':[{'cells':[[1,9]],'values':['999']}]})
 assert bad['state']=='STRUCTURE_REVIEW_REQUIRED' and bad['errors']

def test_validator_accepts_layout_whitespace_and_compatibility_unicode_not_missing_values():
 table={**TABLE,'rows':[[{'row':1,'column':0,'text':'127 m3/second\nTidal mean','ambiguous':False}]]}
 result=validate_proposal(table,{'relationships':[{'cells':[[1,0]],'values':['127 m³/second','Tidal mean']}]})
 assert result['state']=='VERIFIED_STRUCTURE'
