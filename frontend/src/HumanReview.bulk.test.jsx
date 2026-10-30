import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,expect,test,vi} from 'vitest';
import HumanReview,{reviewSummary} from './HumanReview.jsx';

const row={target_id:'e1',kind:'environmental_requirement',condition_id:'one',original_fingerprint:'fingerprint',original:{requirement_text:'Source requirement'},source:{source_verified:true,source_spans:[]},mapping:[],state:'UNREVIEWED',applicability:'APPLICABLE',review:null,effective:null,decision_relevant_default:false,correction_fields:[],bulk_eligible:true};
const data={analysis_run_id:'run',document_sha256:'hash',requirements:[row]};

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();localStorage.clear();});
async function show(records=[row]){
  let current=records;
  const updated=vi.fn();
  const mocked=vi.fn(async(url,options)=>{
    if(!options?.method)return {ok:true,json:async()=>({...data,requirements:current})};
    const review=JSON.parse(options.body).review;
    current=current.map(item=>url.endsWith(item.target_id) ? {...item,state:review.state,applicability:review.applicability,review:{...review,reviewed_at:'now'},effective:['APPROVED','CORRECTED'].includes(review.state) ? item.original : null} : item);
    return {ok:true,json:async()=>({...data,requirements:current})};
  });
  vi.stubGlobal('fetch',mocked);
  render(<HumanReview analysis={{analysis_id:'run'}} session={{boot_id:'boot'}} onUpdated={updated}/>);
  await screen.findByRole('heading',{name:'Condition one'});
  fireEvent.click(screen.getByRole('button',{name:'Multi-select'}));
  fireEvent.click(screen.getByRole('button',{name:'Select all visible'}));
  return {mocked,updated};
}

test('multi-select review asks for confirmation and cancel performs no write',async()=>{
  const {mocked,updated}=await show();
  vi.spyOn(window,'confirm').mockReturnValue(false);
  expect(screen.getByLabelText('Select condition one')).toBeChecked();
  fireEvent.click(screen.getByRole('button',{name:'Save Selected Reviews'}));
  expect(window.confirm).toHaveBeenCalledWith('Save approval and applicability for 1 eligible item(s)? 0 item(s) will be skipped.');
  expect(mocked).toHaveBeenCalledTimes(1);
  expect(updated).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Exit multi-select'}));
  expect(screen.queryByRole('button',{name:'Save Selected Reviews'})).toBeNull();
  expect(screen.getByRole('heading',{name:'Condition one'})).toBeVisible();
  expect(screen.getByText('Pending review',{selector:'.review-badge'})).toBeVisible();
});

test('an unverified selection is explained and cannot be bulk saved',async()=>{
  const {mocked,updated}=await show([{...row,source:{...row.source,source_verified:false}}]);
  const confirm=vi.spyOn(window,'confirm');
  expect(screen.getByLabelText('Select condition one')).toBeChecked();
  expect(screen.getByText('Condition one: Source verification unresolved')).toBeVisible();
  expect(screen.getByText('1 item(s) excluded from this bulk action')).toBeVisible();
  const save=screen.getByRole('button',{name:'Save Selected Reviews'});
  expect(save).toBeDisabled();
  fireEvent.click(save);
  expect(confirm).not.toHaveBeenCalled();
  expect(mocked).toHaveBeenCalledTimes(1);
  expect(updated).not.toHaveBeenCalled();
});

test('confirmed multi-select saves approval and applicability and reports completion',async()=>{
  const {mocked,updated}=await show();
  vi.spyOn(window,'confirm').mockReturnValue(true);
  fireEvent.click(screen.getByRole('button',{name:'Save Selected Reviews'}));
  await screen.findByText('1 item(s) updated.');
  expect(mocked).toHaveBeenCalledTimes(2);
  expect(mocked.mock.calls[1][0]).toBe('/api/reviews/e1');
  const request=mocked.mock.calls[1][1];
  expect(request.method).toBe('PUT');
  expect(request.headers['X-Session-Id']).toBe('boot');
  expect(JSON.parse(request.body)).toMatchObject({analysis_run_id:'run',document_sha256:'hash',review:{state:'APPROVED',applicability:'APPLICABLE',original_fingerprint:'fingerprint'}});
  expect(updated).toHaveBeenCalledTimes(1);
  expect(reviewSummary(updated.mock.calls[0][0].requirements)).toMatchObject({resolved:1,complete:true});
  expect(screen.getByText('0 to check')).toBeVisible();
  expect(mocked.mock.calls.every(([url])=>url.startsWith('/api/reviews'))).toBe(true);
});

test('multi-select saves eligible items and leaves unverified items for individual review',async()=>{
  const skipped={...row,target_id:'e2',condition_id:'two',source:{...row.source,source_verified:false}};
  const {mocked,updated}=await show([row,skipped]);
  vi.spyOn(window,'confirm').mockReturnValue(true);
  expect(screen.getByLabelText('Select condition two')).toBeChecked();
  fireEvent.click(screen.getByRole('button',{name:'Save Selected Reviews'}));
  await screen.findByText('1 item(s) updated. 1 skipped; review them individually.');
  expect(mocked).toHaveBeenCalledTimes(2);
  expect(mocked.mock.calls[1][0]).toBe('/api/reviews/e1');
  const records=updated.mock.calls[0][0].requirements;
  expect(reviewSummary(records)).toMatchObject({resolved:1,complete:false});
  expect(records.find(item=>item.target_id==='e2')).toEqual(skipped);
  expect(screen.getByText('1 to check')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Exit multi-select'}));
  fireEvent.click(screen.getByRole('button',{name:/Review item two/}));
  expect(screen.getByRole('heading',{name:'Condition two'})).toBeVisible();
  expect(screen.getByText('Pending review',{selector:'.review-badge'})).toBeVisible();
});
