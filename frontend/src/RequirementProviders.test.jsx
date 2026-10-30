import React from 'react';
import {render, screen, fireEvent} from '@testing-library/react';
import {describe, it, expect} from 'vitest';
import RequirementProviders from './RequirementProviders.jsx';

const row = {condition_id:'3', canonical_variable:'significant_wave_height', unit:'m', routing:{preferred_provider:'COPERNICUS_MARINE'}};
describe('Requirement and provider mapping', () => {
  it('deduplicates conditions and lists the variables in an expandable source group', () => {
    const {container} = render(<RequirementProviders rows={[row,row,{...row,condition_id:'4',canonical_variable:'mean_wave_period',unit:'s'}]} providers={{COPERNICUS_MARINE:'Credentials required'}}/>);
    expect(screen.getByText('2 requirements · 2 variables')).toBeVisible();
    const details=container.querySelector('details');
    expect(details.open).toBe(false);
    fireEvent.click(details.querySelector('summary'));
    expect(details.open).toBe(true);
    expect(screen.getByText('significant wave height')).toBeVisible();
    expect(screen.getAllByText('Condition 4')[0]).toBeVisible();
    expect(screen.getByText(/configure your Copernicus Marine username and password/)).toBeVisible();
  });
  it('does not claim a configured or mock connector has connected', () => {
    const {rerender} = render(<RequirementProviders rows={[row]} providers={{COPERNICUS_MARINE:'Credentials configured · connection not tested'}}/>);
    expect(screen.getByText('Not connected')).toBeVisible();
    expect(screen.getByText(/Connection not tested yet/)).toBeVisible();
    rerender(<RequirementProviders rows={[row]} mock providers={{COPERNICUS_MARINE:'Connected · retrieval completed'}}/>);
    expect(screen.getByText('Not connected')).toBeVisible();
  });
  it('reports a completed live retrieval as connected', () => {
    render(<RequirementProviders rows={[row]} providers={{COPERNICUS_MARINE:'Connected · retrieval completed; evidence suitability still checked separately'}}/>);
    expect(screen.getByText('Connected')).toBeVisible();
  });
  it('puts capability and matching conditions inside each visible variable', () => {
    const capabilities=[{canonical_variable:'significant_wave_height',display_name:'Significant wave height (Hs)',provider_family:'COPERNICUS_MARINE',implementation_status:'SUPPORTED',unit:'m',notes:'Wave model.'}];
    const renderConditions=items=><div>Matched conditions: {items.map(r=>r.condition_id).join(', ')}</div>;
    const {container}=render(<RequirementProviders rows={[row]} capabilities={capabilities} renderConditions={renderConditions}/>);
    expect(screen.getByText('Significant wave height (Hs)')).toBeVisible();
    expect(screen.queryByText('Environmental Capability Coverage')).toBeNull();
    const variable=container.querySelector('.requirement-variable');
    expect(variable.open).toBe(false);
    fireEvent.click(variable.querySelector('summary'));
    expect(screen.getByText('Data unit: m')).toBeVisible();
    expect(screen.getByText('SUPPORTED')).toBeVisible();
    expect(screen.getByText('Matched conditions: 3')).toBeVisible();
  });
});
