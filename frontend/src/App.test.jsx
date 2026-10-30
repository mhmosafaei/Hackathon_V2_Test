import React from 'react';
import {render, screen, waitFor, within, act} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, it, expect, vi, afterEach} from 'vitest';
import App, {Results, chartData, categories, phases} from './App.jsx';

// Mock only responsive measurement in jsdom; real charts are inspected in-browser.
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {...actual, ResponsiveContainer: ({children}) => <div>{React.cloneElement(children, {width: 540, height: 260})}</div>};
});
const fixture = () => ({filename: 'sanitized-permit.pdf', page_count: 6, mode: 'MOCK', warnings: [], geofences: [],
  summary: {permit_number: 'DEMO-2026', licensee: 'Example Harbour', authority: 'Example Authority', activity: 'Synthetic works', valid_from: null, valid_until: null},
  key_limits: [{label: 'Example deadline', value: 'Within 24 hours', source_verified: true}],
  conditions: Array.from({length: 22}, (_, i) => ({number: String(i + 1), phase: phases[i % 4],
    requirement: `Synthetic requirement ${i + 1}`, important_limit: null, timing: i % 3 === 0 ? 'Within 24 hours' : null,
    category: categories[i % 7], source_verified: i !== 2, review_state: 'UNREVIEWED',
    source_spans: [{page: 2, quotation: `Original synthetic source ${i + 1}.`}]}))});
afterEach(() => {vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear();});
function network(result = fixture()) {
  const fetch = vi.fn(async url => ({ok: true, json: async () => url === '/api/session' ? {boot_id: 'boot-1', mode: 'MOCK'} : result}));
  vi.stubGlobal('fetch', fetch); return fetch;
}
async function upload() {
  const user = userEvent.setup();
  await user.upload(screen.getByLabelText('Upload permit PDF'), new File(['%PDF-test'], 'test.pdf', {type: 'application/pdf'}));
  await waitFor(() => expect(screen.getByRole('button', {name: 'Analyze', exact: true})).toBeEnabled());
  return user;
}
describe('simple session dashboard', () => {
  it('keeps the complete navigation row and exposes long filenames accessibly', () => {
    network(); render(<App/>);
    const navigation = screen.getByRole('navigation', {name: 'Primary navigation'});
    expect(within(navigation).getByRole('button', {name: 'Permit Intelligence'})).toBeVisible();
    expect(within(navigation).getByRole('button', {name: 'Environmental Intelligence'})).toBeVisible();
    expect(within(navigation).getByRole('button', {name: 'Human Review'})).toBeVisible();
    expect(within(navigation).getByRole('button', {name: 'Decision & Work Windows'})).toBeDisabled();
    expect(within(navigation).getAllByRole('button').map(button=>button.textContent)).toEqual(expect.arrayContaining(['1Permit IntelligenceCurrent','2Human ReviewLocked','3Environmental IntelligenceLocked','4Decision & Work WindowsLocked']));
    const longName = 'very-long-permit-document-name-that-needs-a-readable-clamp.pdf';
    render(<Results analysis={{...fixture(), filename: longName}}/>);
    expect(screen.getByTitle(longName)).toHaveAttribute('title', longName);
    expect(screen.getByTitle(longName)).toHaveClass('document-filename');
  });
  it('displays the supplied PermitPulse branding in the dashboard header',()=>{
    network();render(<App/>);
    const wordmark=screen.getByRole('img',{name:'PermitPulse'});
    expect(wordmark).toHaveAttribute('src',expect.stringContaining('permitpulse-wordmark.png'));
    expect(document.querySelector('.brand-symbol')).toHaveAttribute('src',expect.stringContaining('permitpulse-logo.png'));
    expect(screen.queryByRole('button',{name:'Notifications'})).not.toBeInTheDocument();
    expect(screen.queryByRole('button',{name:'User profile'})).not.toBeInTheDocument();
  });
  it('orders six compact permit facts before limits', () => {
    const {container}=render(<Results analysis={fixture()}/>);
    expect(screen.getByRole('heading',{name:'Basic Information'})).toBeVisible();
    expect(screen.getByRole('heading',{name:'Condition Overview'})).toBeVisible();
    expect(screen.getByRole('button',{name:/Next: Human Review/})).toBeVisible();
    expect([...container.querySelectorAll('.permit-summary-grid .eyebrow')].map(el=>el.textContent)).toEqual([
      'Permit number','Validity','Activity','Licensee','Issuing authority','Total conditions'
    ]);
    expect(screen.queryByText('AI-extracted permit information. Review against the original licence before operational use.')).not.toBeInTheDocument();
  });
  it('keeps permit limits compact without hiding unverified sources', () => {
    render(<Results analysis={{...fixture(), key_limits:[
      {label:'Wind gust STOP threshold',value:'Wind gust > 18 m/s',source_verified:true},
      {label:'Mean wave period',value:'Mean wave period > 8 s',source_verified:false}
    ]}}/>);
    expect(screen.getByText('Wind gust')).toHaveTextContent('STOP threshold');
    expect(screen.getByText('> 18 m/s')).toBeVisible();
    expect(screen.getByText('> 8 s')).toBeVisible();
    expect(screen.getByText('Source verification required')).toBeVisible();
    expect(screen.queryByText('Source quotation verified')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Document actions')).not.toBeInTheDocument();
  });
  it('starts empty and never restores a previous analysis', async () => {
    localStorage.setItem('lastAnalysis', JSON.stringify(fixture())); const fetch = network(); render(<App/>);
    expect(screen.getByText('No permit analyzed yet. Upload a permit to begin.')).toBeVisible();
    expect(screen.getByRole('button', {name: 'Analyze', exact: true})).toBeDisabled();
    expect(screen.queryByText('DEMO-2026')).not.toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  });
  it('uploads once, shows three distinct summary charts, then resets', async () => {
    const fetch = network(); render(<App/>); const user = await upload();
    await user.click(screen.getByRole('button', {name: 'Analyze', exact: true}));
    await screen.findByText('DEMO-2026');
    expect(screen.queryByRole('heading',{name:'Permit conditions'})).not.toBeInTheDocument();
    expect(screen.getAllByTestId('chart')).toHaveLength(3);
    expect(screen.getByText(/1 condition requires source verification/)).toHaveTextContent('Review the original quotations in Human Review.');
    expect(screen.getByRole('button',{name:'Next: Open Human Review'})).toBeVisible();
    expect(document.querySelector('pre')).toBeNull();
    expect(fetch.mock.calls.filter(([url]) => url === '/api/analyze')).toHaveLength(1);
    expect(fetch.mock.calls.every(([url]) => !String(url).includes('stage'))).toBe(true);
    await user.click(screen.getByRole('button', {name: 'New Analysis'}));
    expect(screen.queryAllByTestId('chart')).toHaveLength(0);
    expect(screen.getByRole('button', {name: 'Analyze', exact: true})).toBeDisabled();
  });
  it('derives chart totals locally with fixed phase/category denominators', () => {
    const d = chartData(fixture().conditions);
    expect(d.phase.map(v => v.value)).toEqual([6, 6, 5, 5]);
    expect(d.category.map(v => v.value)).toEqual([4, 3, 3, 3, 3, 3, 3]);
    expect(d.limits.map(v => v.value)).toEqual([8, 14]);
  });
  it('does not mount charts while the permit tab is hidden', () => {
    const {rerender} = render(<Results analysis={fixture()} active={false}/>);
    expect(screen.queryByTestId('chart')).not.toBeInTheDocument();
    rerender(<Results analysis={fixture()} active/>);
    expect(screen.getAllByTestId('chart')).toHaveLength(3);
  });
  it('shows each chart topic once in the permit overview', async () => {
    network(); render(<App/>); const user = await upload(); await user.click(screen.getByRole('button', {name: 'Analyze', exact: true}));
    await screen.findByText('DEMO-2026');
    expect(screen.getByRole('heading', {name: 'Conditions by Phase'})).toBeVisible();
    expect(screen.getByRole('heading', {name: 'Conditions by Requirement Type'})).toBeVisible();
    expect(screen.getByRole('heading', {name: 'Conditions with Explicit Limits'})).toBeVisible();
    expect(screen.queryByText('Permit Conditions by Phase')).not.toBeInTheDocument();
  });
  it('shows a loading state and a safe error without retrying automatically', async () => {
    let finish;
    vi.stubGlobal('fetch', vi.fn(url => url === '/api/session' ? Promise.resolve({ok: true, json: async () => ({boot_id: 'boot-1'})}) : new Promise(resolve => {finish = resolve;})));
    render(<App/>); const user = await upload(); await user.click(screen.getByRole('button', {name: 'Analyze', exact: true}));
    expect(screen.getByRole('status')).toHaveTextContent('Analyzing permit…');
    await act(async () => finish({ok: false}));
    expect(screen.getByRole('alert')).toHaveTextContent('Permit analysis could not be completed.');
    expect(screen.getByRole('button', {name: 'Try Again'})).toBeEnabled();
    expect(fetch.mock.calls.filter(([url]) => url === '/api/analyze')).toHaveLength(1);
  });
  it('clears the active result after a server boot identity changes', async () => {
    let boot = 'boot-1';
    vi.stubGlobal('fetch', vi.fn(async (url, options) => ({
      ok: url === '/api/restore' ? boot === 'boot-1' : true,
      json: async () => url === '/api/session' ? {boot_id: boot} : fixture(),
    })));
    render(<App/>); const user = await upload(); await user.click(screen.getByRole('button', {name: 'Analyze', exact: true}));
    await screen.findByText('DEMO-2026');
    boot = 'boot-2';
    await waitFor(() => expect(screen.queryByText('DEMO-2026')).not.toBeInTheDocument(), {timeout: 4500});
    expect(screen.getByText('No permit analyzed yet. Upload a permit to begin.')).toBeVisible();
  });
});

const geographicFixture = () => ({name: 'Example disposal area', description: 'Explicit synthetic disposal boundary',
  type: 'radius', coordinates_or_boundary: 'Centre 54.123456 N, 5.123456 W; radius 0.5 NM',
  restriction: 'Disposal permitted only within the defined area.', source_pages: [2, 3], source_verified: true,
  source_spans: [{page: 2, quotation: 'Disposal permitted only within the defined area.'}]});

describe('geofence at a glance', () => {
  it('appears for an explicit restriction while preserving the three charts', () => {
    render(<Results analysis={{...fixture(), geofences: [geographicFixture()]}}/>);
    expect(screen.getByTestId('geofence-card')).toBeVisible();
    expect(screen.getByTestId('geofence-summary')).toHaveTextContent('Example disposal area · 0.5 NM radius');
    expect(screen.getAllByTestId('chart')).toHaveLength(3);
  });
  it('is absent for no explicit restriction, including older results without the field', () => {
    const {rerender} = render(<Results analysis={fixture()}/>);
    expect(screen.queryByTestId('geofence-card')).not.toBeInTheDocument();
    const old = fixture(); delete old.geofences;
    rerender(<Results analysis={old}/>);
    expect(screen.queryByTestId('geofence-card')).not.toBeInTheDocument();
  });
  it('shows the count and the source-ordered leading restriction for multiple geofences', () => {
    const restricted = {...geographicFixture(), name: 'Example protected segment', type: 'restricted_segment', coordinates_or_boundary: 'KP 12.3 to KP 14.5'};
    render(<Results analysis={{...fixture(), geofences: [restricted, geographicFixture(), {...geographicFixture(), name: 'Named exclusion area'}]}}/>);
    const summary = screen.getByTestId('geofence-summary');
    expect(summary).toHaveTextContent('3 geographic restrictions');
    expect(summary).toHaveTextContent('Example protected segment');
    expect(summary).not.toHaveTextContent('KP 12.3');
  });
  it('keeps coordinates out of the compact summary even with a coordinate-filled name', () => {
    const g = {...geographicFixture(), name: '54.123456 N, 5.123456 W; 54.999999 N, 5.999999 W'};
    render(<Results analysis={{...fixture(), geofences: [g]}}/>);
    const summary = screen.getByTestId('geofence-summary');
    expect(summary).not.toHaveTextContent('54.123456');
    expect(summary).not.toHaveTextContent('5.999999');
    expect(summary).toHaveTextContent('0.5 NM radius');
  });
  it('expands to show every boundary, restriction and original physical source page', async () => {
    render(<Results analysis={{...fixture(), geofences: [geographicFixture()]}}/>);
    const user = userEvent.setup();
    await user.click(screen.getByTestId('geofence-summary'));
    const card = screen.getByTestId('geofence-card');
    expect(within(card).getByText('Centre 54.123456 N, 5.123456 W; radius 0.5 NM')).toBeVisible();
    expect(within(card).getByText('2, 3')).toBeVisible();
    expect(within(card).getByText('Physical page 2')).toBeVisible();
    expect(within(card).getByText('Source quotation verified · Human review required')).toBeVisible();
  });
  it('New Analysis clears geofence state along with the current permit', async () => {
    network({...fixture(), geofences: [geographicFixture()]}); render(<App/>);
    const user = await upload();
    await user.click(screen.getByRole('button', {name: 'Analyze', exact: true}));
    await screen.findByTestId('geofence-card');
    await user.click(screen.getByRole('button', {name: 'New Analysis'}));
    expect(screen.queryByTestId('geofence-card')).not.toBeInTheDocument();
    expect(screen.getByText('No permit analyzed yet. Upload a permit to begin.')).toBeVisible();
  });
});
