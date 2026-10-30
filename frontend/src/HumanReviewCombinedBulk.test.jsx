import React from 'react';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {test,expect,vi,afterEach} from 'vitest';
import Bulk from './HumanReviewBulkToolbar.jsx';
const row={target_id:'c1',condition_id:1,original_fingerprint:'hash',state:'UNREVIEWED',applicability:'UNASSESSED',source:{source_verified:true}};
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
test('combined save approves and sets applicability while preserving corrections',async()=>{
  const fetcher=vi.fn().mockResolvedValue({ok:true,json:async()=>({requirements:[]})});vi.stubGlobal('fetch',fetcher);vi.spyOn(window,'confirm').mockReturnValue(true);
  render(<Bulk rows={[row,{...row,target_id:'c2',state:'CORRECTED',review:{corrections:{threshold:10}}}]} data={{analysis_run_id:'run',document_sha256:'digest'}} session={{boot_id:'boot'}} onRefresh={()=>{}}/>);
  fireEvent.click(screen.getByRole('button',{name:'Save Selected Reviews'}));
  await screen.findByText('2 item(s) updated.');
  expect(JSON.parse(fetcher.mock.calls[0][1].body).review).toMatchObject({state:'APPROVED',applicability:'APPLICABLE'});
  expect(JSON.parse(fetcher.mock.calls[1][1].body).review).toMatchObject({state:'CORRECTED',applicability:'APPLICABLE',corrections:{threshold:10}});
});
test('Not Applicable requires justification before combined save',()=>{
  render(<Bulk rows={[row]} data={{}} session={{}} onRefresh={()=>{}}/>);
  fireEvent.change(screen.getByLabelText('Bulk Applicability value'),{target:{value:'NOT_APPLICABLE'}});
  expect(screen.getByRole('button',{name:'Save Selected Reviews'})).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Bulk Not Applicable justification'),{target:{value:'Outside planned scope'}});
  expect(screen.getByRole('button',{name:'Save Selected Reviews'})).toBeEnabled();
});

test('unverified items are skipped while other selected reviews are saved',async()=>{
 const fetcher=vi.fn().mockResolvedValue({ok:true,json:async()=>({requirements:[]})});vi.stubGlobal('fetch',fetcher);vi.spyOn(window,'confirm').mockReturnValue(true);
 const excluded={...row,target_id:'unverified',condition_id:5,source:{source_verified:false}};
 render(<Bulk rows={[excluded,row]} data={{analysis_run_id:'run',document_sha256:'digest'}} session={{boot_id:'boot'}} onRefresh={()=>{}}/>);
 expect(screen.getByText('Condition 5: Source verification unresolved')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Save Selected Reviews'})).toBeEnabled();
 fireEvent.click(screen.getByRole('button',{name:'Save Selected Reviews'}));
 await screen.findByText('1 item(s) updated. 1 skipped; review them individually.');
 expect(fetcher).toHaveBeenCalledTimes(1);
 expect(fetcher.mock.calls[0][0]).toBe('/api/reviews/c1');
});
test('an all-excluded selection explains the issue and makes no writes',()=>{
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
 render(<Bulk rows={[{...row,source:{source_verified:false}}]} data={{}} session={{}} onRefresh={()=>{}}/>);
 expect(screen.getByText('1 item(s) excluded from this bulk action')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Save Selected Reviews'})).toBeDisabled();
 expect(fetcher).not.toHaveBeenCalled();
});
