from src.documents.evidence_contract_v2 import inventory,validate,VERSION
T={'id':'p21-t1','page':21,'rows':[[{'row':1,'column':0,'text':'Activity','ambiguous':False},{'row':1,'column':1,'text':'Limit','ambiguous':False}],[{'row':2,'column':0,'text':'A1','ambiguous':False},{'row':2,'column':1,'text':'127 m3/s','ambiguous':False}]]}
def test_stable_ids_and_header_context_rejection():
 i=inventory(T); assert i['cells'][0]['id']=='p21-t1-r1-c0'
 p={'contract_version':VERSION,'claims':[{'value':'127 m³/s','value_cells':['p21-t1-r2-c1'],'context_cells':['p21-t1-r1-c0']}]}
 assert validate(T,p)['results'][0]['outcome']=='REJECTED_UNSUPPORTED'
def test_multicell_value_and_version_guard():
 p={'contract_version':VERSION,'claims':[{'value':'127 m³/s','value_cells':['p21-t1-r2-c1'],'context_cells':['p21-t1-r2-c0']}]}
 assert validate(T,p)['results'][0]['outcome']=='STRUCTURAL_RELATION_VERIFIED'
