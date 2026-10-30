import React from 'react';
import {render,screen,cleanup} from '@testing-library/react';
import {test,expect,afterEach} from 'vitest';
import {ReviewProgress as ReviewDashboard} from './App.jsx';
afterEach(cleanup);
const row={kind:'condition',state:'UNREVIEWED',applicability:'APPLICABLE',source:{source_verified:true}};
test('applicability alone does not display completed readiness',()=>{
 render(<ReviewDashboard rows={[row]} progress={{total:1,resolved:1,complete:true}}/>);
 expect(screen.getByText('REVIEW INCOMPLETE')).toBeTruthy();
 expect(screen.getByRole('progressbar',{name:'Review completion: 0 of 1 items resolved, 1 remaining'})).toBeTruthy();
});
test('approved applicable and justified not-applicable items complete readiness',()=>{
 render(<ReviewDashboard rows={[{...row,state:'APPROVED'},{...row,state:'CORRECTED',applicability:'NOT_APPLICABLE',review:{note:'Outside work scope'}}]}/>);
 expect(screen.getByText('REVIEW COMPLETE')).toBeTruthy();
 expect(screen.getByRole('progressbar',{name:'Review completion: 2 of 2 items resolved, 0 remaining'})).toBeTruthy();
});
test('missing not-applicable justification keeps review incomplete',()=>{
 render(<ReviewDashboard rows={[{...row,state:'APPROVED',applicability:'NOT_APPLICABLE',review:{note:''}}]}/>);
 expect(screen.getByText('REVIEW INCOMPLETE')).toBeTruthy();
});
