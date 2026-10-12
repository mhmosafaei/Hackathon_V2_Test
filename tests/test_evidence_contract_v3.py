from src.documents.evidence_contract_v3 import allowed_ids,schema,classify_v2_reference,VERSION
T={'id':'p1-t1','page':1,'rows':[[{'row':1,'column':0,'text':'H','ambiguous':False}],[{'row':2,'column':0,'text':'A','ambiguous':False}]]}
def test_schema_enum_is_generated_from_inventory():
 ids=allowed_ids(T); s=schema(T); assert ids==['p1-t1-r1-c0','p1-t1-r2-c0']; assert s['properties']['contract_version']['const']==VERSION; assert s['properties']['claims']['items']['properties']['value_cells']['items']['enum']==ids
def test_invalid_or_offbyone_ids_are_not_allowed():
 assert classify_v2_reference(T,'p1-t1-r3-c0')=='OFF_BY_ONE_OR_FABRICATED'
