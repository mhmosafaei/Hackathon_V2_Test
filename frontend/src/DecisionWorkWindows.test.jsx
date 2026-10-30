import React from 'react';
import {render,screen,fireEvent,cleanup,within,waitFor} from '@testing-library/react';
import {afterEach,expect,test,vi} from 'vitest';
import DecisionWorkWindows from './DecisionWorkWindows.jsx';
import App from './App.jsx';

const analysis={analysis_id:'fixture-run',document_sha256:'fixture-hash',filename:'fixture-permit.pdf'};
const rule={requirement_id:'env-0',condition_id:'source-a',gating:true,status:'UNKNOWN',reason_code:'EVIDENCE_MISSING',explanation:'Environmental Fetch required',effective_rule:{variable:'Source-backed variable',operator:'>',threshold:2,unit:'m'},source_spans:[{page:1,quotation:'Exact source clause'}],checks:[],evidence_references:[]};
const interval={start:'2026-10-14T00:00:00Z',end:'2026-10-14T01:00:00Z',status:'UNKNOWN',explanation:'Evidence missing for interval',primary_reason:'EVIDENCE_MISSING',passed_count:0,stop_count:0,unknown_count:1,evidence_gap_count:1,rule_results:[rule]};
const payload={assessment_id:'offline-assessment',current_assessment:interval,timeline:[interval],candidate_windows:[],evidence_gaps:[rule],audit:{requested_start:'2026-10-13T05:00:00Z',horizon_hours:72,duration_hours:4,assessed_at:'2026-10-14T00:00:00Z',interval_semantics:'Native intervals'},disclaimer:'Advisory assessment; no operational authorization.'};

test('historical planning assumption is automatic and disclosed without a mode switch',async()=>{
  const response={...payload,audit:{...payload.audit,demo_turbidity:true,demo_assumptions:[{note:'DEMO ONLY: historical 1.112 FNU is a constant assumption. Future turbidity forecasting will be improved.'}]}};
  const fetch=vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>response});vi.stubGlobal('fetch',fetch);
  render(<DecisionWorkWindows analysis={analysis} environmentalStart="2026-10-13T05:00:00Z" session={{boot_id:'boot',environmental_result:{analysis_id:analysis.analysis_id,requirements:[{canonical_variable:'turbidity',historical_reference:{reference_only:true}}]}}}/>);
  expect(screen.queryByRole('checkbox',{name:/Demo mode/})).toBeNull();
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByText('Current operational decision');
  expect(JSON.parse(fetch.mock.calls[0][1].body).demo_turbidity).toBe(true);
  expect(screen.getByRole('note')).toHaveTextContent('historical turbidity observation is held constant');
  expect(screen.queryByText('Demo work-window assessment')).toBeNull();
});
test('backend diagnostics distinguish approved review from unassessed applicability and available evidence',async()=>{
  const blocked={...rule,reason_code:'APPLICABILITY_UNASSESSED',diagnostics:{condition_id:'source-a',title:'Significant wave height',
    review_status:'APPROVED',applicability_status:'UNASSESSED',source_verified:true,evidence_availability:'AVAILABLE',
    evidence_eligibility:'NOT_EVALUATED_REVIEW_BLOCKED',point_count:73,provider:'COPERNICUS_MARINE',dataset_id:'retained-native-dataset',
    native_units:['m'],normalized_units:['m'],native_time_range:{start:interval.start,end:interval.end},
    stored_temporal_status:'COVERED',stored_spatial_status:'COASTAL_REVIEW_REQUIRED',coastal_review_flag_retained:true,
    stored_spatial_criterion_satisfied:true,distance_km:1,threshold_result:'NOT_EVALUATED',stored_threshold_screening:'TRIGGERED',
    qualification:'Inventory is not acceptance.',issues:[{code:'APPLICABILITY_UNASSESSED',explanation:'Explicit applicability review required.',action:'Review applicability.'}]}};
  const cell={...interval,rule_results:[blocked]};
  await show({...payload,current_assessment:cell,timeline:[cell]});
  const table=screen.getByText('Requirement evidence & review status').closest('section');
  expect(table).toHaveTextContent('APPROVED / UNASSESSED');
  expect(table).toHaveTextContent('AVAILABLE / NOT EVALUATED REVIEW BLOCKED');
  expect(table).toHaveTextContent('NOT_EVALUATED');
  expect(table).toHaveTextContent('retained-native-dataset');
  expect(table).toHaveTextContent('Review applicability.');
  expect(screen.getByText(/Select a time segment to inspect it/)).toBeTruthy();
  const intervals=screen.getByText('Interval details').closest('section');
  const detail=intervals.querySelector('details');
  expect(detail.open).toBe(false);
  fireEvent.click(within(intervals).getByText('1 unresolved constraints'));
  expect(detail.open).toBe(true);
  expect(intervals).toHaveTextContent('applicability is unassessed');
});
test('invalidated session assessment is removed from rendered state without automatic evaluation',()=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  const saved={...payload,audit:{...payload.audit,analysis_run_id:analysis.analysis_id,document_sha256:analysis.document_sha256}};
  const view=render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{decision_result:saved}}/>);
  expect(screen.getByText('72-hour decision timeline')).toBeTruthy();
  view.rerender(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{decision_result:null,invalidated_assessment_id:saved.assessment_id}}/>);
  expect(screen.queryByText('72-hour decision timeline')).toBeNull();
  expect(screen.getByRole('alert')).toHaveTextContent('assessment invalidated');
  expect(fetch).not.toHaveBeenCalled();
});
test.each([24,48,72])('%ih horizon posts and restores from session on reopen',async horizon=>{
  const response={...payload,audit:{...payload.audit,horizon_hours:horizon,analysis_run_id:analysis.analysis_id,document_sha256:analysis.document_sha256}};
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>response});vi.stubGlobal('fetch',fetch);
  const view=render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot'}}/>);
  fireEvent.change(screen.getByLabelText('Timeline horizon'),{target:{value:String(horizon)}});
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByText(`${horizon}-hour decision timeline`);
  expect(JSON.parse(fetch.mock.calls[0][1].body).horizon_hours).toBe(horizon);
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue(String(horizon));
  view.unmount();
  render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot',decision_result:response}}/>);
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue(String(horizon));
  expect(screen.getByText(`${horizon}-hour decision timeline`)).toBeTruthy();
  expect(fetch).toHaveBeenCalledTimes(1);
});
test('specific UNKNOWN reason is consistent across current selected interval and actions; excluded turbidity is separate',async()=>{
  const oxygen={...rule,effective_rule:{canonical_variable:'dissolved_oxygen'},reason_code:'STALE_OXYGEN_EVIDENCE'};
  const turbidity={...rule,requirement_id:'environmental_requirement-1-private',gating:false,
    effective_rule:{canonical_variable:'turbidity'},availability_policy:'AVAILABLE_EVIDENCE_ONLY_MVP',
    explanation:'Turbidity evidence stale — excluded from MVP work-window decision for this interval.'};
  const cell={...interval,rule_results:[oxygen,turbidity]};
  await show({...payload,current_assessment:cell,timeline:[cell],evidence_gaps:[oxygen]});
  const text='Insufficient evidence: Dissolved oxygen data is stale.';
  for(const title of ['Current operational decision','Selected window details','Interval details','Missing evidence & required actions'])
    expect(within(screen.getByText(title).closest('section')).getByText(text)).toBeTruthy();
  expect(screen.getByText(turbidity.explanation)).toBeTruthy();
  expect(screen.queryByText('environmental_requirement-1-private')).toBeNull();
});
test('late session result and successful response synchronize controls to actual audit without auto evaluation',async()=>{
  const returned={...payload,audit:{...payload.audit,analysis_run_id:analysis.analysis_id,document_sha256:analysis.document_sha256,horizon_hours:24,duration_hours:6,ranking:'longest',include_conditional:true,requested_start:'2026-10-13T05:00:00Z'}};
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>returned});vi.stubGlobal('fetch',fetch);
  const accepted=vi.fn();
  const view=render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot'}} onEvaluated={accepted}/>);
  view.rerender(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot',decision_result:{...returned,audit:{...returned.audit,horizon_hours:72,duration_hours:2,requested_start:null}}}} onEvaluated={accepted}/>);
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue('72');
  expect(screen.getByLabelText('Required continuous duration')).toHaveValue('2');
  expect(screen.getByLabelText('Start (UTC)')).toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByText('24-hour decision timeline');
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue('24');
  expect(screen.getByLabelText('Required continuous duration')).toHaveValue('6');
  expect(screen.getByLabelText('Rank candidates')).toHaveValue('longest');
  expect(screen.getByLabelText('Start (UTC)')).toHaveValue('2026-10-13T05:00');
  expect(screen.getByLabelText('Include conditional windows requiring additional verification')).toBeChecked();
  expect(accepted).toHaveBeenCalledWith(returned);
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('stored informational direction values appear in non-gating inspector without Fetch',()=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  const direction={...rule,gating:false,status:'WORK',reason_code:'OUT_OF_SCOPE_FOR_MVP_DECISION',informational_evidence:{status:'INFORMATIONAL',derived:true,points:[{value:90,valid_time:interval.start}],qualification:'Audit only'},evidence_references:[{provider:'COPERNICUS_MARINE',dataset_id:'native-current'}]};
  const stored={...payload,current_assessment:{...interval,rule_results:[direction]},audit:{...payload.audit,analysis_run_id:analysis.analysis_id,document_sha256:analysis.document_sha256}};
  render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{decision_result:stored}}/>);
  expect(screen.getByText(/Derived from Copernicus U\/V/)).toBeTruthy();
  expect(screen.getByTestId('informational-direction')).toHaveTextContent('90');
  expect(screen.getByText(/No threshold/)).toBeTruthy();
  expect(fetch).not.toHaveBeenCalled();
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();localStorage.clear();});
async function show(result=payload,environmentalStart='2026-10-13T05:00:00Z'){const mocked=vi.fn().mockResolvedValue({ok:true,json:async()=>result});vi.stubGlobal('fetch',mocked);render(<DecisionWorkWindows environmentalStart={environmentalStart} analysis={analysis} session={{boot_id:'boot'}}/>);fireEvent.click(screen.getByText('Evaluate existing evidence'));await screen.findByText('72-hour decision timeline');return mocked;}

test('STOP naming agrees across current, selected window, timeline and interval table without mutating F09',async()=>{
  const triggered={...rule,status:'STOP',effective_rule:{variable:'significant wave height',canonical_variable:'significant_wave_height'}};
  const stopped={...interval,status:'STOP',rule_results:[triggered],explanation:'One or more reviewed operational constraints are triggered.'};
  const value={...payload,current_assessment:stopped,timeline:[stopped],evidence_gaps:[]};
  const before=JSON.stringify(value);
  await show(value);
  const reason='Triggered constraint: Significant wave height';
  for(const heading of ['Current operational decision','Operational assessment','Selected window details','Interval details']){
    expect(within(screen.getByText(heading).closest('section')).getByText(reason)).toBeTruthy();
  }
  fireEvent.click(screen.getByRole('button',{name:/STOP 14 Oct 2026 · 00:00 UTC/}));
  expect(within(screen.getByText('Selected window details').closest('section')).getByText(reason)).toBeTruthy();
  expect(JSON.stringify(value)).toBe(before);
});
test('Decision navigation follows Human Review',()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({boot_id:'boot'})}));render(<App/>);const navigation=screen.getByRole('navigation',{name:'Primary navigation'});const labels=within(navigation).getAllByRole('button').map(button=>button.querySelector('span')?.textContent);expect(labels.slice(-3)).toEqual(['Human Review','Environmental Intelligence','Decision & Work Windows']);});

test('summary STOP rows and selected windows use distinct matching interval triggers',async()=>{
  const generic='One or more reviewed operational constraints are triggered.';
  const a={...interval,start:'2026-10-13T05:00:00Z',end:'2026-10-13T06:00:00Z',status:'STOP',explanation:generic};
  const b={...a,start:a.end,end:'2026-10-13T07:00:00Z'};
  delete a.rule_results; delete b.rule_results;
  const parent=(variable,states)=>({...rule,status:'STOP',effective_rule:{canonical_variable:variable},
    interval_results:states.map(([cell,status])=>({...rule,start:cell.start,end:cell.end,status}))});
  const wave=parent('significant_wave_height',[[a,'STOP'],[b,'WORK']]);
  const gust=parent('wind_gust',[[a,'WORK'],[b,'STOP']]);
  wave.interval_results.forEach(r=>delete r.effective_rule);
  gust.interval_results.forEach(r=>delete r.effective_rule);
  const value={...payload,current_assessment:{...a,end:b.end,rule_results:[wave,gust]},timeline:[a,b],evidence_gaps:[]};
  const before=JSON.stringify(value);
  await show(value);
  expect(within(screen.getByText('Selected window details').closest('section')).getByText('Triggered constraints: Significant wave height, Wind gust')).toBeTruthy();
  const table=within(screen.getByText('Interval details').closest('section'));
  const rows=table.getAllByRole('row');
  expect(rows[1]).toHaveTextContent('Triggered constraint: Significant wave height');
  expect(rows[1]).not.toHaveTextContent('Wind gust');
  expect(rows[2]).toHaveTextContent('Triggered constraint: Wind gust');
  fireEvent.click(screen.getByRole('button',{name:/STOP 13 Oct 2026 · 05:00 UTC/}));
  expect(within(screen.getByText('Selected window details').closest('section')).getByText('Triggered constraint: Significant wave height')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:/STOP 13 Oct 2026 · 06:00 UTC/}));
  expect(within(screen.getByText('Selected window details').closest('section')).getByText('Triggered constraint: Wind gust')).toBeTruthy();
  expect(JSON.stringify(value)).toBe(before);
});
test.each(['WORK','STOP','UNKNOWN'])('renders %s assessment explanation and actual UTC interval',async state=>{await show({...payload,current_assessment:{...interval,status:state}});expect(screen.getAllByText(state).length).toBeGreaterThan(0);expect(screen.getAllByText(state === 'WORK' ? 'Evidence missing for interval' : state === 'STOP' ? 'One or more reviewed operational constraints are triggered.' : 'Insufficient evidence: Source-backed variable data is unavailable.').length).toBeGreaterThan(0);expect(screen.getByRole('button',{name:/UNKNOWN 14 Oct 2026 · 00:00 UTC/})).toBeTruthy();expect(screen.getByText(/No operational authorization/)).toBeTruthy();expect(screen.queryByText(/ILLUSTRATIVE|Belfast/)).toBeNull();});
test('controls apply explicit duration horizon conditional and ranking without provider Fetch',async()=>{const mocked=await show();fireEvent.change(screen.getByLabelText('Required continuous duration'),{target:{value:'6'}});fireEvent.change(screen.getByLabelText('Timeline horizon'),{target:{value:'24'}});fireEvent.click(screen.getByLabelText('Include conditional windows requiring additional verification'));fireEvent.change(screen.getByLabelText('Rank candidates'),{target:{value:'longest'}});fireEvent.click(screen.getByText('Evaluate existing evidence'));expect(JSON.parse(mocked.mock.calls[1][1].body)).toMatchObject({duration_hours:6,horizon_hours:24,include_conditional:true,ranking:'longest'});expect(mocked.mock.calls.every(([url])=>url==='/api/decision/evaluate')).toBe(true);});
test('timeline selection displays inspector source and missing actions',async()=>{await show();fireEvent.click(screen.getByRole('button',{name:/UNKNOWN 14 Oct 2026 · 00:00 UTC/}));expect(screen.getByText('Constraint inspector')).toBeTruthy();expect(screen.getByText('Exact source clause',{exact:false})).toBeTruthy();expect(screen.getAllByText('Environmental Fetch required').length).toBeGreaterThan(0);expect(screen.getByText('Missing evidence & required actions')).toBeTruthy();});
test('candidate click opens interval details',async()=>{await show({...payload,candidate_windows:[{start:interval.start,end:interval.end,duration_hours:6,type:'CONDITIONAL',status:'UNKNOWN',unknown_count:1}]});fireEvent.click(screen.getByRole('button',{name:/CONDITIONAL \/ UNKNOWN/}));expect(within(screen.getByText('Selected window details').closest('section')).getByText('Insufficient evidence: Source-backed variable data is unavailable.')).toBeTruthy();});
test('mount never dispatches and errors are visible without retry',async()=>{const mocked=vi.fn().mockResolvedValue({ok:false,json:async()=>({error:'DECISION_INPUT_OR_REVIEW_INVALID'})});vi.stubGlobal('fetch',mocked);render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot'}}/>);expect(mocked).not.toHaveBeenCalled();fireEvent.click(screen.getByText('Evaluate existing evidence'));expect(await screen.findByRole('alert')).toHaveTextContent('DECISION_INPUT_OR_REVIEW_INVALID');expect(mocked).toHaveBeenCalledTimes(1);});
test('unavailable backend gives actionable 404 message without retry',async()=>{const mocked=vi.fn().mockResolvedValue({ok:false,status:404});vi.stubGlobal('fetch',mocked);render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot'}}/>);fireEvent.click(screen.getByText('Evaluate existing evidence'));expect(await screen.findByRole('alert')).toHaveTextContent('Restart the backend with the Decision API enabled');expect(mocked).toHaveBeenCalledTimes(1);});
test('draft controls do not relabel evaluated results',async()=>{await show();fireEvent.change(screen.getByLabelText('Timeline horizon'),{target:{value:'24'}});fireEvent.click(screen.getByRole('button',{name:'2 h'}));expect(screen.getByRole('status')).toHaveTextContent('72-hour horizon / 4-hour minimum duration');expect(screen.getByText('72-hour decision timeline')).toBeTruthy();expect(screen.getByText('Interval details')).toBeTruthy();expect(screen.getByText('Operational assessment')).toBeTruthy();});
test('selected native measurements are shown without invented metrics',async()=>{await show({...payload,current_assessment:{...interval,rule_results:[{...rule,checks:[{values:[{value:1.2,unit:'m',valid_time:interval.start}]}]}]}});expect(screen.getByText('1.2 m')).toBeTruthy();expect(screen.getByText('Recorded native values')).toBeTruthy();});
test('formats inspector measurements but preserves reviewed thresholds and coordinates',async()=>{
  const measured={...rule,effective_rule:{...rule.effective_rule,threshold:8.1234567},
    checks:[{operator:'>',threshold:8.1234567,unit:'m',values:[{value:1.23456,unit:'m',valid_time:interval.start}]}],
    evidence_references:[{evidence_id:'native-1',provider:'COPERNICUS_MARINE',dataset_id:'synthetic',
      dataset_variable:'VHM0',latitude:54.123456,longitude:-6.654321,distance_km:12.34567,
      selected_depth_m:5.55555,temporal_resolution:'PT1H',spatial_resolution:'synthetic'}]};
  const reviewedThreshold={...rule,requirement_id:'env-threshold',
    effective_rule:{...rule.effective_rule,threshold:9.87654321},checks:[]};
  const cell={...interval,rule_results:[measured,reviewedThreshold]};
  await show({...payload,current_assessment:cell,timeline:[cell]});
  fireEvent.click(screen.getByRole('button',{name:/UNKNOWN 14 Oct 2026 · 00:00 UTC/}));

  const inspector=screen.getByText('Constraint inspector').closest('section');
  expect(inspector.textContent).toContain('1.235 m');
  expect(inspector.textContent).toContain('12.346 km');
  expect(inspector.textContent).toContain('5.556 m');
  expect(inspector.textContent).toContain('54.123456, -6.654321');
  expect(inspector.textContent).toContain('> 8.1234567 m triggers');
  expect(inspector.textContent).toContain('> 9.87654321 m');
  for(const unrounded of ['1.23456','12.34567','5.55555']) {
    expect(document.body.textContent).not.toContain(unrounded);
  }
});
test('reference sections keep real selectable windows and a separate inspector',async()=>{await show({...payload,candidate_windows:[{...interval,duration_hours:6,type:'CONDITIONAL'}]});const window=screen.getByRole('button',{name:/CONDITIONAL \/ UNKNOWN/});fireEvent.click(window);expect(window).toHaveAttribute('aria-pressed','true');expect(screen.getByText('Selected window details').closest('section')).toHaveClass('decision-selected');expect(screen.getByText('Constraint inspector').closest('section')).toHaveClass('decision-inspector');expect(screen.getByText('Work-window finder').closest('section')).toHaveClass('decision-finder');expect(screen.queryByText(/Demonstration: authorized/)).toBeNull();});
test('MVP gating and audit-only requirements are visibly separated',async()=>{await show({...payload,current_assessment:{...interval,rule_results:[rule,{...rule,requirement_id:'audit-only',gating:false,reason_code:'OUT_OF_SCOPE_FOR_MVP_DECISION'}]}});expect(screen.getByText('Gating constraints & time / position prerequisites')).toBeTruthy();expect(screen.getByText('Non-gating requirements · retained for audit')).toBeTruthy();expect(screen.queryByText(/they are not legally irrelevant/)).toBeNull();});

test.each(['2026-10-13T05:00','2026-10-13T05:00:15'])('all controls including explicit UTC %s are serialized',async start=>{
  const mocked=await show(payload,`${start}Z`);
  expect(screen.getByLabelText('Start (UTC)')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Timeline horizon'),{target:{value:'24'}});
  fireEvent.change(screen.getByLabelText('Required continuous duration'),{target:{value:'6'}});
  fireEvent.change(screen.getByLabelText('Rank candidates'),{target:{value:'longest'}});
  fireEvent.click(screen.getByLabelText('Include conditional windows requiring additional verification'));
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  const body=JSON.parse(mocked.mock.calls[1][1].body);
  expect(body).toEqual({analysis_run_id:analysis.analysis_id,document_sha256:analysis.document_sha256,
    start:expect.any(String),horizon_hours:24,duration_hours:6,ranking:'longest',include_conditional:true});
  expect(new Date(body.start).toISOString()).toBe(new Date(`${start}Z`).toISOString());
});

test('session refresh does not overwrite current results or drafts; remount restores evaluated controls',async()=>{
  const saved={...payload,audit:{...payload.audit,analysis_run_id:analysis.analysis_id,document_sha256:analysis.document_sha256,
    horizon_hours:24,duration_hours:6,ranking:'longest',include_conditional:true,requested_start:'2026-10-13T05:00:00Z'}};
  const mocked=vi.fn();vi.stubGlobal('fetch',mocked);
  const view=render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot',decision_result:saved}}/>);
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue('24');
  expect(screen.getByLabelText('Required continuous duration')).toHaveValue('6');
  expect(screen.getByLabelText('Rank candidates')).toHaveValue('longest');
  expect(screen.getByLabelText('Start (UTC)')).toHaveValue('2026-10-13T05:00');
  expect(screen.getByLabelText('Include conditional windows requiring additional verification')).toBeChecked();
  fireEvent.change(screen.getByLabelText('Required continuous duration'),{target:{value:'2'}});
  view.rerender(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot',decision_result:payload}}/>);
  expect(screen.getByLabelText('Required continuous duration')).toHaveValue('2');
  expect(screen.getByText('24-hour decision timeline')).toBeTruthy();
  expect(mocked).not.toHaveBeenCalled();
  view.unmount();
  render(<DecisionWorkWindows environmentalStart="2026-10-13T05:00:00Z" analysis={analysis} session={{boot_id:'boot',decision_result:saved}}/>);
  expect(screen.getByLabelText('Required continuous duration')).toHaveValue('6');
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue('24');
  expect(mocked).not.toHaveBeenCalled();
});

test('requires the previous step time instead of falling back to a different run or the current time',()=>{
  const mocked=vi.fn();vi.stubGlobal('fetch',mocked);
  render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot',decision_result:{...payload,audit:{...payload.audit,analysis_run_id:'other',document_sha256:'other'}}}}/>);
  expect(screen.getByLabelText('Start (UTC)')).toBeVisible();
  expect(screen.getByText(/Confirm the planned period in Environmental Intelligence/)).toBeVisible();
  expect(screen.getByText('Evaluate existing evidence')).toBeDisabled();
  expect(mocked).not.toHaveBeenCalled();
});

test('inherits the previous step time, defaults to 72h and exposes only three finder selects',()=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  const view=render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot'}} environmentalStart="2026-10-31T00:00:00Z"/>);
  expect(screen.getByLabelText('Start (UTC)')).toBeVisible();
  expect(screen.getByLabelText('Start (UTC)')).toHaveValue('2026-10-31T00:00');
  const finder=screen.getByText('Work-window finder').closest('section');
  expect(within(finder).getAllByRole('combobox')).toHaveLength(3);
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue('72');
  view.rerender(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot'}} environmentalStart="2026-11-01T00:00:00Z"/>);
  expect(screen.getByLabelText('Start (UTC)')).toHaveValue('2026-11-01T00:00');
  expect(fetch).not.toHaveBeenCalled();
});
test('restores environmental query start only from the matching analysis',()=>{
  const view=render(<DecisionWorkWindows analysis={analysis} session={{environmental_result:{analysis_id:analysis.analysis_id,query:{start_time:'2026-10-31T00:00:00Z'}}}}/>);
  expect(screen.getByLabelText('Start (UTC)')).toHaveValue('2026-10-31T00:00');
  view.unmount();
  render(<DecisionWorkWindows analysis={analysis} session={{environmental_result:{analysis_id:'another-run',query:{start_time:'2026-10-31T00:00:00Z'}}}}/>);
  expect(screen.getByLabelText('Start (UTC)')).toBeVisible();
});

test('scrolls and focuses results only after an explicit successful evaluation',async()=>{
  const original=HTMLElement.prototype.scrollIntoView;
  const scroll=vi.fn();HTMLElement.prototype.scrollIntoView=scroll;
  try {
    const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>payload});vi.stubGlobal('fetch',fetch);
    render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot'}} environmentalStart="2026-10-31T00:00:00Z"/>);
    expect(scroll).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('Evaluate existing evidence'));
    await waitFor(()=>expect(scroll).toHaveBeenCalledWith(expect.objectContaining({block:'start'})));
    expect(screen.getByRole('region',{name:'Assessment results'})).toHaveFocus();
    expect(screen.getByRole('region',{name:'Assessment results'}).style.scrollMarginTop).toBe('16px');
    const count=scroll.mock.calls.length;
    fetch.mockResolvedValueOnce({ok:false,json:async()=>({error:'Evaluation failed'})});
    fireEvent.click(screen.getByText('Evaluate existing evidence'));
    await screen.findByRole('alert');
    expect(scroll).toHaveBeenCalledTimes(count);
  } finally {if(original)HTMLElement.prototype.scrollIntoView=original;else delete HTMLElement.prototype.scrollIntoView;}
});


test('technical sections are collapsed while the timeline and candidates stay visible',async()=>{
  await show({...payload,evidence_gaps:[]});
  for(const title of ['Evidence and review details','Assessment breakdown','Timeline interval details','Rules, sources and audit','Selected-window measurements','Evidence gaps and actions (0)']){
    const summary=screen.getByText(title,{selector:'summary'});
    expect(summary.parentElement.open).toBe(false);
  }
  expect(screen.getByText('72-hour decision timeline')).toBeVisible();
  expect(screen.getByText('Candidate continuous windows')).toBeVisible();
  const summary=screen.getByText('Evidence and review details',{selector:'summary'});
  fireEvent.click(summary);
  expect(summary.parentElement.open).toBe(true);
  expect(screen.getByText('Requirement evidence & review status')).toBeVisible();
});

test('unresolved actions and explicitly selected measurements are expanded',async()=>{
  await show();
  expect(screen.getByText('Evidence gaps and actions (1)',{selector:'summary'}).parentElement.open).toBe(true);
  const selection=screen.getByText('Selected-window measurements',{selector:'summary'}).parentElement;
  expect(selection.open).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:/UNKNOWN 14 Oct 2026 · 00:00 UTC/}));
  expect(selection.open).toBe(true);
});


test('edited UTC start is sent only on Evaluate and survives session polling',async()=>{
  const response={...payload,audit:{...payload.audit,requested_start:'2026-10-31T08:30:15Z'}};
  const mocked=vi.fn().mockResolvedValue({ok:true,json:async()=>response});vi.stubGlobal('fetch',mocked);
  const view=render(<DecisionWorkWindows analysis={analysis} environmentalStart="2026-10-31T00:00:00Z" session={{boot_id:'boot'}}/>);
  fireEvent.change(screen.getByLabelText('Start (UTC)'),{target:{value:'2026-10-31T08:30:15'}});
  view.rerender(<DecisionWorkWindows analysis={analysis} environmentalStart="2026-10-31T00:00:00Z" session={{boot_id:'boot',provider_status:{}}}/>);
  expect(Date.parse(screen.getByLabelText('Start (UTC)').value+'Z')).toBe(Date.parse('2026-10-31T08:30:15Z'));
  expect(mocked).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByText('72-hour decision timeline');
  expect(JSON.parse(mocked.mock.calls[0][1].body).start).toBe('2026-10-31T08:30:15Z');
  fireEvent.change(screen.getByLabelText('Start (UTC)'),{target:{value:''}});
  expect(screen.getByText('Evaluate existing evidence')).toBeDisabled();
  view.rerender(<DecisionWorkWindows analysis={analysis} environmentalStart="2026-11-01T00:00:00Z" session={{boot_id:'boot'}}/>);
  expect(screen.getByLabelText('Start (UTC)')).toHaveValue('2026-11-01T00:00');
});


test('timeline axis labels the actual 72-hour UTC period and readable candidate dates',async()=>{
  const cell={...interval,start:'2026-11-05T14:00:00Z',end:'2026-11-08T14:00:00Z'};
  const data={...payload,current_assessment:cell,timeline:[cell],candidate_windows:[{...cell,duration_hours:72,type:'CONDITIONAL'}]};
  const before=JSON.stringify(data);
  await show(data);
  const axis=screen.getByRole('group',{name:'Timeline time axis (UTC)'});
  const ticks=axis.querySelectorAll('time');
  expect(ticks).toHaveLength(7);
  expect(ticks[0]).toHaveAttribute('datetime','2026-11-05T14:00:00.000Z');
  expect(ticks[0]).toHaveTextContent('05 Nov14:00');
  expect(ticks[6]).toHaveAttribute('datetime','2026-11-08T14:00:00.000Z');
  expect(ticks[6]).toHaveTextContent('08 Nov14:00');
  const candidate=screen.getByRole('button',{name:/CONDITIONAL \/ UNKNOWN/});
  expect(candidate).toHaveTextContent('05 Nov 2026 · 14:00 UTC — 08 Nov 2026 · 14:00 UTC');
  expect(JSON.stringify(data)).toBe(before);
});
