import {expect, test} from 'vitest';
import {decisionExplanation, intervalRuleResults} from './decisionReason.js';

const trigger = (variable, extra={}) => ({gating:true, status:'STOP',
  requirement_id:'environmental_requirement-0-internal',effective_rule:{canonical_variable:variable}, ...extra});
const stop = rule_results => ({status:'STOP', rule_results});

test('singular trigger uses human title, never identifier',()=>{
  expect(decisionExplanation(stop([trigger('significant_wave_height')]))).toBe('Triggered constraint: Significant wave height');
});
test('multiple triggers are deduplicated and deterministically alphabetized',()=>{
  const rules=[trigger('wind_gust'),trigger('turbidity'),trigger('significant_wave_height'),trigger('wind_gust'),
    trigger('visibility',{gating:false}),trigger('mean_wave_period',{status:'WORK'})];
  const expected='Triggered constraints: Significant wave height, Turbidity, Wind gust';
  expect(decisionExplanation(stop(rules))).toBe(expected);
  expect(decisionExplanation(stop([...rules].reverse()))).toBe(expected);
});
test('unknown names retain the generic STOP fallback and hide IDs',()=>{
  expect(decisionExplanation(stop([trigger(null,{effective_rule:{variable:'environmental_requirement-0-private'}})])))
    .toBe('One or more reviewed operational constraints are triggered.');
});
test.each(['WORK'])('%s text is unchanged and input is not mutated',status=>{
  const value={status,explanation:'Original advisory explanation',rule_results:[trigger('wind_gust')]};
  const original=JSON.stringify(value);
  expect(decisionExplanation(value)).toBe(value.explanation);
  expect(JSON.stringify(value)).toBe(original);
});

test('UNKNOWN names and categorizes only blocking rules with stable deduplication',()=>{
  const missing=(variable,reason_code)=>({...trigger(variable),status:'UNKNOWN',reason_code});
  const rules=[missing('surface_current_speed','EVIDENCE_MISSING'),missing('dissolved_oxygen','STALE_OXYGEN_EVIDENCE'),
    missing('significant_wave_height','TEMPORAL_COVERAGE_INSUFFICIENT'),missing('surface_current_speed','EVIDENCE_MISSING'),
    {...missing('turbidity','STALE_TURBIDITY_EVIDENCE'),gating:false}];
  const result={status:'UNKNOWN',rule_results:rules};
  const text=decisionExplanation(result);
  expect(text).toBe('Insufficient evidence: Dissolved oxygen data is stale; Significant wave height does not cover this interval; Surface current speed data is unavailable.');
  expect(decisionExplanation({...result,rule_results:[...rules].reverse()})).toBe(text);
  expect(text).not.toMatch(/Turbidity|environmental_requirement/);
  expect(decisionExplanation({status:'UNKNOWN'})).toBe('Insufficient evidence for one or more required operational constraints.');
});
test('reviewed variable title fallback and component capitalization',()=>{
  const value=stop([trigger(null,{effective_rule:{variable:'eastward current component u'}})]);
  expect(decisionExplanation(value)).toBe('Triggered constraint: Eastward current component U');
});

test('summary interval resolves only its own evaluated children, not aggregate STOPs',()=>{
  const a={start:'2026-10-13T05:00:00Z',end:'2026-10-13T06:00:00Z',status:'STOP'};
  const b={start:a.end,end:'2026-10-13T07:00:00Z',status:'STOP'};
  const parent=(variable,states)=>({...trigger(variable),interval_results:states.map(([interval,status])=>({...interval,status,gating:true}))});
  const payload={timeline:[a,b],current_assessment:{rule_results:[
    parent('significant_wave_height',[[a,'STOP'],[b,'WORK']]),
    parent('wind_gust',[[a,'WORK'],[b,'STOP']]),
  ]}};
  const before=JSON.stringify(payload);
  expect(decisionExplanation(a,'',payload)).toBe('Triggered constraint: Significant wave height');
  expect(decisionExplanation(b,'',payload)).toBe('Triggered constraint: Wind gust');
  expect(decisionExplanation({...a,end:b.end},'',payload)).toBe('Triggered constraints: Significant wave height, Wind gust');
  expect(JSON.stringify(payload)).toBe(before);
});

test('own rule data takes precedence and no matching bounds keeps fallback',()=>{
  const own=stop([trigger('turbidity')]);
  expect(intervalRuleResults(own,{})).toBe(own.rule_results);
  expect(decisionExplanation({status:'STOP',start:'2026-10-13T08:00:00Z',end:'2026-10-13T09:00:00Z'},'',{}))
    .toBe('One or more reviewed operational constraints are triggered.');
});
