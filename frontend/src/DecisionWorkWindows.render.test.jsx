import React from 'react';
import {render, screen, fireEvent, within, cleanup, waitFor} from '@testing-library/react';
import {afterEach, expect, test, vi} from 'vitest';
import DecisionWorkWindows from './DecisionWorkWindows.jsx';
import {decisionTime} from './decisionTime.js';

const analysis={analysis_id:'render-run',document_sha256:'render-hash',filename:'offline.pdf'};
const start='2026-10-13T00:00:00Z';
const at=hours=>new Date(Date.parse(start)+hours*3600000).toISOString();
const window=(a,b)=>({start:at(a),end:at(b),status:'WORK',type:'VERIFIED',duration_hours:b-a,unknown_count:0});
function response({duration=2,horizon=24,ranking='earliest',offset=0,windows=[window(0,2)],requested=start}={}){
  const cell={start:at(offset),end:at(offset+horizon),status:'WORK',explanation:'All evaluated constraints pass.',
    rule_results:[],passed_count:1,stop_count:0,unknown_count:0,evidence_gap_count:0};
  return {assessment_id:`${duration}-${horizon}-${ranking}-${offset}`,current_assessment:{...cell,end:at(offset+duration)},
    timeline:[cell],candidate_windows:windows,evidence_gaps:[],disclaimer:'Advisory only; no operational authorization.',
    audit:{analysis_run_id:analysis.analysis_id,document_sha256:analysis.document_sha256,
      start:at(offset),requested_start:requested,horizon_hours:horizon,duration_hours:duration,ranking,
      include_conditional:false,assessed_at:start,interval_semantics:'Stored evidence only'}};
}
async function setup(initial, next){
  const fetch=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>initial})
    .mockResolvedValueOnce({ok:true,json:async()=>next});
  vi.stubGlobal('fetch',fetch);
  render(<DecisionWorkWindows analysis={analysis} environmentalStart={start} session={{boot_id:'boot'}}/>);
  fireEvent.change(screen.getByLabelText('Required continuous duration'),{target:{value:'2'}});
  fireEvent.change(screen.getByLabelText('Timeline horizon'),{target:{value:'24'}});
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByText('24-hour decision timeline');
  await waitFor(()=>expect(screen.getByText('Evaluate existing evidence')).not.toBeDisabled());
  return fetch;
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test('POST 200 replaces rendered 2h result immediately with distinct returned 6h result',async()=>{
  const first=response(), next=response({duration:6,windows:[window(3,9)]});
  const before=JSON.stringify([first,next]);
  const fetch=await setup(first,next);
  expect(screen.getByRole('button',{name:/2 continuous hours/})).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Required continuous duration'),{target:{value:'6'}});
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByRole('button',{name:/6 continuous hours/});
  expect(screen.queryByRole('button',{name:/2 continuous hours/})).toBeNull();
  expect(screen.getByText('Evaluated minimum duration: 6 hours.')).toBeTruthy();
  const selected=screen.getByText('Selected window details').closest('section');
  expect(selected).toHaveTextContent(`${decisionTime(at(0))} — ${decisionTime(at(6))}`);
  expect(screen.getByText('Current operational decision').closest('section')).toHaveTextContent(decisionTime(at(6)));
  expect(fetch).toHaveBeenCalledTimes(2); // No session response is needed to render POST output.
  expect(JSON.stringify([first,next])).toBe(before);
});

test('returned 24h to 72h response visibly replaces timeline and audit horizon',async()=>{
  await setup(response(),response({horizon:72}));
  expect(screen.getByRole('button',{name:`WORK ${decisionTime(at(0))} to ${decisionTime(at(24))}`})).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Timeline horizon'),{target:{value:'72'}});
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByText('72-hour decision timeline');
  expect(screen.queryByRole('button',{name:`WORK ${decisionTime(at(0))} to ${decisionTime(at(24))}`})).toBeNull();
  expect(screen.getByRole('button',{name:`WORK ${decisionTime(at(0))} to ${decisionTime(at(72))}`})).toBeTruthy();
});

test('returned longest ranking replaces visible candidate order, without client re-ranking',async()=>{
  const short=window(0,2),long=window(4,10);
  await setup(response({windows:[short,long]}),response({ranking:'longest',windows:[long,short]}));
  const candidates=()=>within(screen.getByText('Candidate continuous windows').closest('section')).getAllByRole('button');
  expect(candidates()[0]).toHaveTextContent('2 continuous hours');
  fireEvent.change(screen.getByLabelText('Rank candidates'),{target:{value:'longest'}});
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await waitFor(()=>expect(candidates()[0]).toHaveTextContent('6 continuous hours'));
  expect(candidates()[1]).toHaveTextContent('2 continuous hours');
});

test('explicit start response visibly replaces current, selected and timeline intervals',async()=>{
  await setup(response(),response({offset:5,requested:at(5),windows:[window(5,7)]}));
  fireEvent.change(screen.getByLabelText('Start (UTC)'),{target:{value:'2026-10-13T05:00'}});
  fireEvent.click(screen.getByText('Evaluate existing evidence'));
  await screen.findByRole('button',{name:`WORK ${decisionTime(at(5))} to ${decisionTime(at(29))}`});
  expect(screen.getByText('Current operational decision').closest('section')).toHaveTextContent(decisionTime(at(5)));
  expect(screen.getByText('Selected window details').closest('section')).toHaveTextContent(`${decisionTime(at(5))} — ${decisionTime(at(7))}`);
  expect(screen.queryByRole('status')).toBeNull();
});
