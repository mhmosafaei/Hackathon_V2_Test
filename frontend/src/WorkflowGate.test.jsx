import React from 'react';
import {render, screen, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {it, expect, vi, afterEach, beforeEach} from 'vitest';
import App from './App.jsx';

vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {...actual, ResponsiveContainer: ({children}) => <div>{React.cloneElement(children, {width: 540, height: 260})}</div>};
});
vi.mock('./Environmental.jsx', () => ({default: () => <div>Environmental view</div>}));
vi.mock('./HumanReview.jsx', async importOriginal => ({...(await importOriginal()), default: ({onUpdated,onLoaded}) => <div>
  <button onClick={() => onLoaded({analysis_run_id:'run-1',requirements:[{state:'APPROVED',applicability:'APPLICABLE',conflict:null,review:{note:''},source:{source_verified:true},kind:'condition'}]})}>Report loaded review</button>
  <button onClick={() => onLoaded({analysis_run_id:'run-1',review_progress:{total:2,resolved:0,remaining:2,complete:false},requirements:[
    {state:'UNREVIEWED',applicability:'APPLICABLE',conflict:null,source:{source_verified:true},kind:'condition'},
    {state:'UNREVIEWED',applicability:'UNASSESSED',conflict:null,source:{source_verified:true},kind:'spatial_context'}
  ]})}>Report applicability-only review</button>
  <button onClick={() => onUpdated({analysis_run_id:'run-1', review_progress:{total:1,resolved:1,remaining:0,complete:true},requirements:[{state:'APPROVED',applicability:'APPLICABLE',conflict:null,review:{note:''},source:{source_verified:true},kind:'condition'}]})}>Complete review</button>
  <button onClick={() => onUpdated({analysis_run_id:'run-1', review_progress:{total:1,resolved:0,remaining:1,complete:false},requirements:[{state:'UNREVIEWED',applicability:'APPLICABLE',conflict:null,source:{source_verified:true},kind:'condition'}]})}>Change review to pending</button>
</div>}));
vi.mock('./DecisionWorkWindows.jsx', () => ({default: ({reviewReady,assessmentStale,onEvaluated}) => <div>
  <span>{reviewReady ? 'Decision ready' : 'Review required before decision'}</span>
  {assessmentStale && <span>Assessment out of date</span>}
  <button onClick={() => onEvaluated({assessment_id:'new-assessment'})}>Reevaluate</button>
</div>}));

const analysis = {analysis_id:'run-1',document_sha256:'a'.repeat(64),filename:'test.pdf',page_count:1,
  summary:{permit_number:'P-1',licensee:'Test',authority:'Test',activity:'Test',valid_from:null,valid_until:null},
  conditions:[],key_limits:[],geofences:[],warnings:[]};
beforeEach(()=>{vi.spyOn(window,'scrollTo').mockImplementation(()=>{});});
afterEach(() => {vi.restoreAllMocks();vi.unstubAllGlobals();localStorage.clear();sessionStorage.clear();});

it('unlocks after review, keeps review editable, and marks later changes stale', async () => {
  const scroll = window.scrollTo;
  vi.stubGlobal('fetch', vi.fn(async url => ({ok:true,json:async () => url==='/api/session'
    ? {boot_id:'boot-1'} : url.startsWith('/api/reviews?')
      ? {analysis_run_id:'run-1',review_progress:{total:1,resolved:0,remaining:1,complete:false},requirements:[{state:'UNREVIEWED',applicability:'APPLICABLE',conflict:null,source:{source_verified:true},kind:'condition'}]}
      : analysis})));
  const user=userEvent.setup();render(<App/>);
  await user.upload(screen.getByLabelText('Upload permit PDF'),new File(['%PDF-test'],'test.pdf',{type:'application/pdf'}));
  await user.click(screen.getByRole('button',{name:'Analyze',exact:true}));
  await screen.findByText('P-1');
  const nav=screen.getByRole('navigation',{name:'Primary navigation'});
  expect(within(nav).getByRole('button',{name:'Environmental Intelligence'})).toBeDisabled();
  expect(within(nav).getByRole('button',{name:'Decision & Work Windows'})).toBeDisabled();
  expect(screen.getByText('Review key permit details and limits here')).toBeVisible();
  await user.click(within(nav).getByRole('button',{name:'Human Review'}));
  expect(screen.getByText('Human Review: Check the interpretation')).toBeVisible();
  expect(screen.getByText('Please resolve every AI-extracted item to unlock Environmental Intelligence and downstream decision assessment.')).toBeVisible();
  expect(screen.getByRole('button',{name:'Back: Permit Intelligence'})).toBeVisible();
  expect(screen.queryByRole('heading',{name:'Human Review'})).not.toBeInTheDocument();
  expect(screen.queryByText('Review the AI-extracted permit interpretation before it is used by downstream decision assessment.')).not.toBeInTheDocument();
  expect(within(screen.getByRole('region',{name:'Step 2 guidance'})).getByLabelText('Review status summary')).toBeVisible();
  expect(within(screen.getByLabelText('Review status summary')).getAllByText(/Pending review|Rejected|Source \/ review gaps/)).toHaveLength(3);
  expect(screen.getByText('0 of 1 resolved · 1 remaining')).toBeVisible();
  await user.click(screen.getByRole('button',{name:'Complete review'}));
  expect(screen.getByText('1 of 1 resolved · 0 remaining')).toBeVisible();
  expect(document.querySelector('.workflow-review-completion')).toBeNull();
  expect(within(nav).getByRole('button',{name:'Environmental Intelligence'})).toBeEnabled();
  expect(within(nav).getByRole('button',{name:'Decision & Work Windows'})).toBeDisabled();
  await user.click(within(nav).getByRole('button',{name:'Environmental Intelligence'}));
  expect(screen.getByText('Environmental Intelligence: extract and fetch environmental data')).toBeVisible();
  await user.click(screen.getAllByRole('button',{name:'Continue with evidence gap'})[0]);
  expect(within(nav).getByRole('button',{name:'Decision & Work Windows'})).toBeEnabled();
  await user.click(screen.getAllByRole('button',{name:'Next: Decision & Work Windows'}).at(-1));
  expect(scroll).toHaveBeenCalledWith({top:0,left:0,behavior:'instant'});
  expect(screen.getByRole('heading',{name:'Decision & Work Windows'})).toHaveFocus();
  expect(screen.getByText('Decision ready')).toBeVisible();
  await user.click(within(nav).getByRole('button',{name:'Human Review'}));
  await user.click(screen.getByRole('button',{name:'Change review to pending'}));
  expect(within(nav).getByRole('button',{name:'Environmental Intelligence'})).toBeDisabled();
  expect(within(nav).getByRole('button',{name:'Decision & Work Windows'})).toBeDisabled();
  await user.click(screen.getByRole('button',{name:'Complete review'}));
  expect(within(nav).getByRole('button',{name:'Decision & Work Windows'})).toBeEnabled();
  await user.click(within(nav).getByRole('button',{name:'Decision & Work Windows'}));
  expect(screen.getByText('Decision ready')).toBeVisible();
  expect(screen.getByText('Assessment out of date')).toBeVisible();
  await user.click(screen.getByRole('button',{name:'Reevaluate'}));
  await waitFor(()=>expect(screen.queryByText('Assessment out of date')).not.toBeInTheDocument());
});

it('explains that applicable items still need interpretation review before Step 3', async () => {
  vi.stubGlobal('fetch', vi.fn(async url => ({ok:true,json:async () => url==='/api/session'
    ? {boot_id:'boot-1'} : url.startsWith('/api/reviews?')
      ? {analysis_run_id:'run-1',review_progress:{total:2,resolved:0,remaining:2,complete:false},requirements:[]}
      : analysis})));
  const user=userEvent.setup();render(<App/>);
  await user.upload(screen.getByLabelText('Upload permit PDF'),new File(['%PDF-test'],'test.pdf',{type:'application/pdf'}));
  await user.click(screen.getByRole('button',{name:'Analyze',exact:true}));
  await screen.findByText('P-1');
  await user.click(within(screen.getByRole('navigation',{name:'Primary navigation'})).getByRole('button',{name:'Human Review'}));
  await user.click(screen.getByRole('button',{name:'Report applicability-only review'}));
  expect(screen.getAllByRole('button',{name:'Next: Environmental Intelligence'})[0]).toHaveAttribute('title',expect.stringContaining('2 interpretations need approval or correction'));
  expect(screen.getAllByRole('button',{name:'Next: Environmental Intelligence'}).every(button => button.disabled)).toBe(true);
});


it('uses the completed review already loaded on the Human Review page when the parent request fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url.startsWith('/api/reviews?')) throw new Error('Transient parent request failure');
    return {ok:true,json:async () => url==='/api/session' ? {boot_id:'boot-1'} : analysis};
  }));
  const user=userEvent.setup();render(<App/>);
  await user.upload(screen.getByLabelText('Upload permit PDF'),new File(['%PDF-test'],'test.pdf',{type:'application/pdf'}));
  await user.click(screen.getByRole('button',{name:'Analyze',exact:true}));
  await screen.findByText('P-1');
  const nav=screen.getByRole('navigation',{name:'Primary navigation'});
  await user.click(within(nav).getByRole('button',{name:'Human Review'}));
  expect(within(nav).getByRole('button',{name:'Environmental Intelligence'})).toBeDisabled();
  await user.click(screen.getByRole('button',{name:'Report loaded review'}));
  expect(within(nav).getByRole('button',{name:'Environmental Intelligence'})).toBeEnabled();
  expect(screen.getByText('1 of 1 resolved · 0 remaining')).toBeVisible();
  const ring = screen.getByRole('img',{name:/Applicability: 1 applicable, 0 not applicable, 0 unassessed/});
  expect(ring).toBeVisible();
  expect(ring.style.getPropertyValue('--applicable-end')).toBe('360deg');
  expect(ring.style.getPropertyValue('--not-applicable-end')).toBe('360deg');
  expect(screen.getByText('Applicable').parentElement).toHaveTextContent('1');
  await user.click(within(nav).getByRole('button',{name:'Environmental Intelligence'}));
  await user.click(screen.getAllByRole('button',{name:'Continue with evidence gap'})[0]);
  await user.click(within(nav).getByRole('button',{name:'Decision & Work Windows'}));
  expect(screen.getByText('Decision ready')).toBeVisible();
});
