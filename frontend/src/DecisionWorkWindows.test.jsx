import React from 'react';
import {render,screen,fireEvent,cleanup,within} from '@testing-library/react';
import {afterEach,expect,test,vi} from 'vitest';
import DecisionWorkWindows from './DecisionWorkWindows.jsx';
import App from './App.jsx';

const analysis={analysis_id:'fixture-run',document_sha256:'fixture-hash',filename:'fixture-permit.pdf'};
const rule={requirement_id:'env-0',condition_id:'source-a',gating:true,status:'UNKNOWN',reason_code:'EVIDENCE_MISSING',explanation:'Environmental Fetch required',effective_rule:{variable:'Source-backed variable',operator:'>',threshold:2,unit:'m'},source_spans:[{page:1,quotation:'Exact source clause'}],checks:[],evidence_references:[]};
const interval={start:'2026-10-14T00:00:00Z',end:'2026-10-14T01:00:00Z',status:'UNKNOWN',explanation:'Evidence missing for interval',primary_reason:'EVIDENCE_MISSING',passed_count:0,stop_count:0,unknown_count:1,evidence_gap_count:1,rule_results:[rule]};
const payload={assessment_id:'offline-assessment',current_assessment:interval,timeline:[interval],candidate_windows:[],evidence_gaps:[rule],audit:{horizon_hours:72,duration_hours:4,assessed_at:'2026-10-14T00:00:00Z',interval_semantics:'Native intervals'},disclaimer:'Advisory assessment; no operational authorization.'};
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();localStorage.clear();});
async function show(result=payload){const mocked=vi.fn().mockResolvedValue({ok:true,json:async()=>result});vi.stubGlobal('fetch',mocked);render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot'}}/>);fireEvent.click(screen.getByText('Evaluate existing evidence'));await screen.findByText('72-hour decision timeline');return mocked;}

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
  fireEvent.click(screen.getByRole('button',{name:/STOP 2026-10-14T00:00:00Z/}));
  expect(within(screen.getByText('Selected window details').closest('section')).getByText(reason)).toBeTruthy();
  expect(JSON.stringify(value)).toBe(before);
});
test('Decision navigation follows Human Review',()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({boot_id:'boot'})}));render(<App/>);const buttons=within(screen.getByRole('navigation')).getAllByRole('button');expect(buttons.map(b=>b.textContent).slice(-2)).toEqual(['Human Review','Decision & Work Windows']);});

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
  fireEvent.click(screen.getByRole('button',{name:/STOP 2026-10-13T05:00:00Z/}));
  expect(within(screen.getByText('Selected window details').closest('section')).getByText('Triggered constraint: Significant wave height')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:/STOP 2026-10-13T06:00:00Z/}));
  expect(within(screen.getByText('Selected window details').closest('section')).getByText('Triggered constraint: Wind gust')).toBeTruthy();
  expect(JSON.stringify(value)).toBe(before);
});
test.each(['WORK','STOP','UNKNOWN'])('renders %s assessment explanation and actual UTC interval',async state=>{await show({...payload,current_assessment:{...interval,status:state}});expect(screen.getAllByText(state).length).toBeGreaterThan(0);expect(screen.getAllByText('Evidence missing for interval').length).toBeGreaterThan(0);expect(screen.getByRole('button',{name:/UNKNOWN 2026-10-14T00:00:00Z/})).toBeTruthy();expect(screen.getByText(/No regulatory approval, legal compliance/)).toBeTruthy();expect(screen.queryByText(/ILLUSTRATIVE|Belfast/)).toBeNull();});
test('controls apply explicit duration horizon conditional and ranking without provider Fetch',async()=>{const mocked=await show();fireEvent.change(screen.getByLabelText('Required continuous duration'),{target:{value:'6'}});fireEvent.change(screen.getByLabelText('Timeline horizon'),{target:{value:'24'}});fireEvent.click(screen.getByLabelText('Include conditional windows requiring additional verification'));fireEvent.change(screen.getByLabelText('Rank candidates'),{target:{value:'longest'}});fireEvent.click(screen.getByText('Evaluate existing evidence'));expect(JSON.parse(mocked.mock.calls[1][1].body)).toMatchObject({duration_hours:6,horizon_hours:24,include_conditional:true,ranking:'longest'});expect(mocked.mock.calls.every(([url])=>url==='/api/decision/evaluate')).toBe(true);});
test('timeline selection displays inspector source and missing actions',async()=>{await show();fireEvent.click(screen.getByRole('button',{name:/UNKNOWN 2026-10-14T00:00:00Z/}));expect(screen.getByText('Constraint inspector')).toBeTruthy();expect(screen.getByText('Exact source clause',{exact:false})).toBeTruthy();expect(screen.getAllByText('Environmental Fetch required').length).toBeGreaterThan(0);expect(screen.getByText('Missing evidence & required actions')).toBeTruthy();});
test('candidate click opens interval details',async()=>{await show({...payload,candidate_windows:[{start:interval.start,end:interval.end,duration_hours:6,type:'CONDITIONAL',status:'UNKNOWN',unknown_count:1}]});fireEvent.click(screen.getByRole('button',{name:/CONDITIONAL \/ UNKNOWN/}));expect(screen.getByText('Additional verification is required.')).toBeTruthy();});
test('mount never dispatches and errors are visible without retry',async()=>{const mocked=vi.fn().mockResolvedValue({ok:false,json:async()=>({error:'DECISION_INPUT_OR_REVIEW_INVALID'})});vi.stubGlobal('fetch',mocked);render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot'}}/>);expect(mocked).not.toHaveBeenCalled();fireEvent.click(screen.getByText('Evaluate existing evidence'));expect(await screen.findByRole('alert')).toHaveTextContent('DECISION_INPUT_OR_REVIEW_INVALID');expect(mocked).toHaveBeenCalledTimes(1);});
test('unavailable backend gives actionable 404 message without retry',async()=>{const mocked=vi.fn().mockResolvedValue({ok:false,status:404});vi.stubGlobal('fetch',mocked);render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot'}}/>);fireEvent.click(screen.getByText('Evaluate existing evidence'));expect(await screen.findByRole('alert')).toHaveTextContent('Restart the backend with the Decision API enabled');expect(mocked).toHaveBeenCalledTimes(1);});
test('draft controls do not relabel evaluated results',async()=>{await show();fireEvent.change(screen.getByLabelText('Timeline horizon'),{target:{value:'24'}});fireEvent.click(screen.getByRole('button',{name:'2 h'}));expect(screen.getByRole('status')).toHaveTextContent('72-hour horizon / 4-hour minimum duration');expect(screen.getByText('72-hour decision timeline')).toBeTruthy();expect(screen.getByText('Interval details')).toBeTruthy();expect(screen.getByText('Operational assessment')).toBeTruthy();});
test('selected native measurements are shown without invented metrics',async()=>{await show({...payload,current_assessment:{...interval,rule_results:[{...rule,checks:[{values:[{value:1.2,unit:'m',valid_time:interval.start}]}]}]}});expect(screen.getByText('1.2 m')).toBeTruthy();expect(screen.getByText('Recorded native values')).toBeTruthy();});
test('reference sections keep real selectable windows and a separate inspector',async()=>{await show({...payload,candidate_windows:[{...interval,duration_hours:6,type:'CONDITIONAL'}]});const window=screen.getByRole('button',{name:/CONDITIONAL \/ UNKNOWN/});fireEvent.click(window);expect(window).toHaveAttribute('aria-pressed','true');expect(screen.getByText('Selected window details').closest('section')).toHaveClass('decision-selected');expect(screen.getByText('Constraint inspector').closest('section')).toHaveClass('decision-inspector');expect(screen.getByText('Work-window finder').closest('section')).toHaveClass('decision-finder');expect(screen.queryByText(/Demonstration: authorized/)).toBeNull();});
test('MVP gating and audit-only requirements are visibly separated',async()=>{await show({...payload,current_assessment:{...interval,rule_results:[rule,{...rule,requirement_id:'audit-only',gating:false,reason_code:'OUT_OF_SCOPE_FOR_MVP_DECISION'}]}});expect(screen.getByText('Gating constraints & time / position prerequisites')).toBeTruthy();expect(screen.getByText('Non-gating requirements · retained for audit')).toBeTruthy();expect(screen.getByText(/they are not legally irrelevant/)).toBeTruthy();});

test.each(['2026-10-13T05:00','2026-10-13T05:00:15'])('all controls including explicit UTC %s are serialized',async start=>{
  const mocked=await show();
  fireEvent.change(screen.getByLabelText('Start UTC'),{target:{value:start}});
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
  const view=render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot',decision_result:saved}}/>);
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue('24');
  expect(screen.getByLabelText('Required continuous duration')).toHaveValue('6');
  expect(screen.getByLabelText('Rank candidates')).toHaveValue('longest');
  expect(screen.getByLabelText('Start UTC')).toHaveValue('2026-10-13T05:00');
  expect(screen.getByLabelText('Include conditional windows requiring additional verification')).toBeChecked();
  fireEvent.change(screen.getByLabelText('Required continuous duration'),{target:{value:'2'}});
  view.rerender(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot',decision_result:payload}}/>);
  expect(screen.getByLabelText('Required continuous duration')).toHaveValue('2');
  expect(screen.getByText('24-hour decision timeline')).toBeTruthy();
  expect(mocked).not.toHaveBeenCalled();
  view.unmount();
  render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot',decision_result:saved}}/>);
  expect(screen.getByLabelText('Required continuous duration')).toHaveValue('6');
  expect(screen.getByLabelText('Timeline horizon')).toHaveValue('24');
  expect(mocked).not.toHaveBeenCalled();
});

test('blank start stays null and does not inherit another run decision',async()=>{
  const mocked=vi.fn().mockResolvedValue({ok:true,json:async()=>payload});vi.stubGlobal('fetch',mocked);
  render(<DecisionWorkWindows analysis={analysis} session={{boot_id:'boot',decision_result:{...payload,audit:{...payload.audit,analysis_run_id:'other',document_sha256:'other'}}}}/>);
  expect(screen.getByLabelText('Start UTC')).toHaveValue('');
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByText('72-hour decision timeline');
  expect(JSON.parse(mocked.mock.calls[0][1].body).start).toBeNull();
});
