import React from 'react';
import {render,screen,fireEvent,within} from '@testing-library/react';
import {it,expect} from 'vitest';
import RequirementProviders from './RequirementProviders.jsx';
const row={condition_id:'3',canonical_variable:'significant_wave_height',requirement_text:'Full condition wording must stay in Human Review.',unit:'m',routing:{preferred_provider:'COPERNICUS_MARINE',implemented:true}};
it('shows three source cards and expandable variable data without condition wording',()=>{
  render(<RequirementProviders rows={[row,row]} providers={{COPERNICUS_MARINE:'Credentials required'}}/>);
  expect(screen.getByRole('article',{name:'Copernicus Marine'})).toBeVisible();
  expect(screen.getByRole('article',{name:'ECMWF Forecast'})).toBeVisible();
  expect(screen.getByRole('article',{name:'Historical / ERA5'})).toBeVisible();
  expect(screen.getAllByTestId('environment-variable')).toHaveLength(1);
  expect(document.querySelector('.requirement-total')).toHaveTextContent('1requirements');
  fireEvent.click(screen.getByText('significant wave height'));
  expect(screen.getByText('Permit unit: m')).toBeVisible();
  expect(screen.queryByText(row.requirement_text)).toBeNull();
  expect(screen.getByText('Conditions:').parentElement).toHaveTextContent('Conditions: 3');
});
it('labels credentials as configured without claiming a retrieval',()=>{
  const {rerender}=render(<RequirementProviders rows={[row]} providers={{COPERNICUS_MARINE:'Credentials configured · connection not tested'}}/>);
  expect(screen.getByText('Credentials configured')).toBeVisible();
  expect(screen.queryByText('Live retrieval completed.')).toBeNull();
  rerender(<RequirementProviders rows={[row]} mock providers={{COPERNICUS_MARINE:'Connected · retrieval completed'}}/>);
  expect(screen.getAllByText('Offline preview')).toHaveLength(3);
  expect(screen.queryByText('Live retrieval completed.')).toBeNull();
});
it('reports actual completed retrieval separately from credential configuration',()=>{
  render(<RequirementProviders rows={[row]} providers={{COPERNICUS_MARINE:'Connected · retrieval completed'}}/>);
  expect(screen.getByText('Live retrieval completed.')).toBeVisible();
});
it('keeps capability and any required manual data control inside the variable',()=>{
  const capabilities=[{canonical_variable:'significant_wave_height',display_name:'Significant wave height (Hs)',implementation_status:'SUPPORTED',unit:'m',notes:'Wave model.'}];
  render(<RequirementProviders rows={[row]} capabilities={capabilities} renderVariableDetails={()=> <label>Manual data<input/></label>}/>);
  fireEvent.click(screen.getByText('Significant wave height (Hs)'));
  expect(screen.getByText('Data unit: m')).toBeVisible();
  expect(screen.getByText('SUPPORTED')).toBeVisible();
  expect(screen.getByLabelText('Manual data')).toBeVisible();
  expect(screen.queryByText('Environmental Capability Coverage')).toBeNull();
});
it('retains external required variables without adding a fourth provider card',()=>{
  render(<RequirementProviders rows={[{...row,canonical_variable:'local_measurement',routing:{preferred_provider:'EXTERNAL'}}]}/>);
  expect(document.querySelectorAll('.requirement-provider-card')).toHaveLength(3);
  expect(screen.getByText('local measurement')).toBeVisible();
  fireEvent.click(screen.getByText('local measurement'));
  expect(screen.getByText('Live retrieval is not configured for this variable.')).toBeVisible();
});
