import React from 'react';
import {render, screen, waitFor, act, fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, it, expect, vi, afterEach} from 'vitest';
import Environmental, {blockerLabel} from './Environmental.jsx';
import App from './App.jsx';

vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {...actual, ResponsiveContainer: ({children}) => <div>{React.cloneElement(children, {width:540,height:260})}</div>};
});
const row = {condition_id:'4',source_page:2,requirement_text:'Wave height shall not exceed 2.5 m.',
  canonical_variable:'significant_wave_height', operator:'<=',threshold:2.5,unit:'m',source_verified:true,
  source_spans:[{page:2,quotation:'Original synthetic requirement.'}],
  routing:{preferred_provider:'COPERNICUS_MARINE',potential_source_variables:[]},status:'INSUFFICIENT_DATA',
  notes_for_evaluation:'Additional location and operational timing required.'};
const doc = () => ({analysis_id:'fresh', filename:'synthetic-environment.pdf',mode:'MOCK',page_count:2,warnings:[],
  summary:{permit_number:'TEST-ENV'},conditions:[],key_limits:[],geofences:[],
  environmental_requirements:[row],environmental_mapping:[row]});
const session = {boot_id:'boot',mode:'MOCK',provider_status:{COPERNICUS_MARINE:'Credentials required',ECMWF_FORECAST:'Public endpoint configured · connection not tested'}};
afterEach(() => {vi.restoreAllMocks();vi.unstubAllGlobals();});

describe('environmental evidence view', () => {
  it('has a clean empty state before analysis', () => {
    render(<Environmental session={session}/>);
    expect(screen.getByText('Analyze a permit to identify its environmental evidence requirements.')).toBeVisible();
    expect(screen.queryByRole('button',{name:'Fetch Environmental Data'})).toBeNull();
  });
  it('does not fetch random weather if no requirements exist', () => {
    const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
    render(<Environmental session={session} analysis={{...doc(),environmental_requirements:[],environmental_mapping:[]}}/>);
    expect(screen.getByText('No explicit environmental data requirements were identified in this permit.')).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });
  it('renders multiple requirements, source pages and provider states without fetching', async () => {
    const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
    render(<Environmental session={session} analysis={{...doc(),environmental_requirements:[row,row],environmental_mapping:[row,{...row,condition_id:'5',canonical_variable:'ais_status',routing:{preferred_provider:'EXTERNAL'},status:'EXTERNAL_EVIDENCE_REQUIRED'}]}}/>);
    expect(screen.getAllByTestId('environment-row')).toHaveLength(2);
    expect(screen.getByText(/Credentials required/)).toBeVisible();
    expect(screen.getByText('EXTERNAL EVIDENCE REQUIRED')).toBeVisible();
    await userEvent.click(screen.getAllByText('Source and retrieval notes')[0]);
    expect(screen.getAllByText('Page 2: Original synthetic requirement.')[0]).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });
  it('counts unique authoritative mapped conditions, not raw model rows', () => {
    const duplicate = {...row, condition_id:'38', canonical_variable:'sea_surface_temperature'};
    render(<Environmental session={session} analysis={{...doc(), environmental_requirements:[row, row, duplicate], environmental_mapping:[duplicate, {...duplicate, operator:'>'}]}}/>);
    expect(screen.getByText('Environmental Requirements').parentElement).toHaveTextContent('1');
  });
  it('requires an explicit Fetch click and renders mocked evidence', async () => {
    const evidence={...row,status:'WITHIN_THRESHOLD',evidence:{provider:'COPERNICUS_MARINE',dataset_name:'Synthetic fixture',dataset_id:'SYNTHETIC',
      data_type:'MODEL_FORECAST',latitude:54,longitude:-6,depth:0,retrieved_at:'2026-10-12T12:00:00Z',
      points:[{data_time:'2026-10-12T12:00:00Z',raw_value:1.2,unit:'m',normalized_value:1.2,normalized_unit:'m',status:'WITHIN_THRESHOLD'}]}};
    const fetch=vi.fn(async()=>({ok:true,json:async()=>({requirements:[evidence],provider_status:session.provider_status})}));vi.stubGlobal('fetch',fetch);
    render(<Environmental session={session} analysis={doc()}/>);
    expect(fetch).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
    await screen.findByTestId('evidence-card');
    expect(fetch).toHaveBeenCalledTimes(1);
    const body=JSON.parse(fetch.mock.calls[0][1].body);
    expect(body.analysis_id).toBe('fresh');expect(body.start_time).toBeNull();expect(body.latitude).toBeNull();
    expect(screen.getByText('Retrieved point / representative model value (not a compliance conclusion)')).toBeVisible();
    expect(screen.getByText('1.2 m', {selector: 'strong'})).toBeVisible();
    expect(screen.queryByText('SAFE TO OPERATE')).not.toBeInTheDocument();
  });
  it('restores a session-associated result without fetching', () => {
    const evidence={...row,status:'WITHIN_THRESHOLD',evidence:{provider:'COPERNICUS_MARINE',dataset_name:'Session cache',dataset_id:'SYNTHETIC',
      data_type:'MODEL_FORECAST',latitude:54,longitude:-6,depth:0,retrieved_at:'2026-10-12T12:00:00Z',
      points:[{data_time:'2026-10-12T12:00:00Z',raw_value:1.2,unit:'m',normalized_value:1.2,normalized_unit:'m',status:'WITHIN_THRESHOLD'}]}};
    const fetch=vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<Environmental session={{...session, environmental_result:{analysis_id:'fresh',requirements:[evidence],evidence_groups:[evidence],provider_status:session.provider_status,executable_rules:0}}} analysis={doc()}/>);
    expect(screen.getByTestId('evidence-card')).toBeVisible();
    expect(screen.getByText('1.2 m', {selector:'strong'})).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });
  it('shows source geofences but never guesses a midpoint', async () => {
    render(<Environmental session={session} analysis={{...doc(),geofences:[{name:'Synthetic cable route',type:'route',coordinates_or_boundary:'Source endpoints only',source_pages:[3,4]}]}}/>);
    await userEvent.click(screen.getByText('Source geographic restrictions · 1'));
    expect(screen.getByText('Synthetic cable route',{selector:'b'})).toBeVisible();
    expect(screen.getByLabelText('Latitude')).toHaveValue(null);
    expect(screen.getByText(/Routes and large areas: spatial sampling strategy required/)).toBeVisible();
  });
  it.each([48,192])('renders %i populated source records in a compact points table',async(count)=>{
    const points=Array.from({length:count},(_,i)=>({data_time:`2026-10-12T${String(Math.floor(i/4)%24).padStart(2,'0')}:${String(i%4*15).padStart(2,'0')}:00Z`,raw_value:0.1+i/1000,unit:'m/s',normalized_value:0.1+i/1000,normalized_unit:'m/s',status:'INSUFFICIENT_DATA'}));
    const fetch=vi.fn(async()=>({ok:true,json:async()=>({requirements:[{...row,evidence:{provider:'COPERNICUS_MARINE',dataset_id:'SYNTHETIC',points}}]})}));vi.stubGlobal('fetch',fetch);
    render(<Environmental session={session} analysis={doc()}/>);
    await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
    await userEvent.click(await screen.findByText(`All retrieved points · ${count}`));
    const records=screen.getAllByTestId('retrieved-point');expect(records).toHaveLength(count);
    for(const record of records) expect(record.querySelectorAll('td')[0].textContent).toContain('2026-10-12T');
    expect(records[0].querySelectorAll('td')[1].textContent).toContain('0.1 m/s');
    expect(screen.getAllByText(/NOT DETERMINED —/).length).toBeGreaterThan(0);
    expect(screen.queryByText('WITHIN THRESHOLD')).toBeNull();
  });
  it('does not retry provider failures', async () => {
    const fetch=vi.fn(async()=>({ok:false}));vi.stubGlobal('fetch',fetch);
    render(<Environmental session={session} analysis={doc()}/>);
    await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
    await screen.findByRole('alert');expect(fetch).toHaveBeenCalledTimes(1);
  });
  it.each(['sea_surface_temperature','air_temperature'])('renders one %s evidence card with both checks and separate query provenance',async(variable)=>{
    const evidence={provider:'COPERNICUS_MARINE',dataset_id:'SYNTHETIC',data_type:'MODEL_FORECAST',
      requested_coordinates:[54,-6],latitude:54.01,longitude:-6.01,spatial_resolution:'1.5 km',distance_km:1.2,
      quality_status:'COASTAL_REVIEW_REQUIRED',max_representative_distance_km:5,
      coverage:{requested_start:'2026-10-12T16:41Z',requested_end:'2026-10-13T16:41Z',
        provider_query_start:'2026-10-12T16:00Z',provider_query_end:'2026-10-13T17:00Z',
        actual_start:'2026-10-12T16:00Z',actual_end:'2026-10-13T17:00Z',temporal_resolution_seconds:3600},
      points:[{data_time:'2026-10-12T16:00Z',raw_value:14.3,unit:'C',comparison:false}]};
    evidence.temporal_coverage_status='COVERED';evidence.retrieval_status='SUCCESS';
    evidence.qualification='Coastal applicability requires human review. Not a compliance conclusion.';
    const a={...row,status:'THRESHOLD_EXCEEDED',canonical_variable:variable,operator:'<',threshold:2,unit:'C',evidence};
    const b={...a,operator:'>',threshold:22};
    const fetch=vi.fn(async()=>({ok:true,json:async()=>({requirements:[a,b],evidence_groups:[{...a,checks:[a,b]}]})}));vi.stubGlobal('fetch',fetch);
    render(<Environmental session={session} analysis={doc()}/>);
    await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
    expect(await screen.findAllByTestId('evidence-card')).toHaveLength(1);
    expect(screen.getAllByTestId('environment-row')).toHaveLength(2);
    expect(screen.getAllByTestId('threshold-check')).toHaveLength(2);
    expect(screen.getByText('COVERED')).toBeVisible();
    expect(screen.getAllByText(/NOT TRIGGERED/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Coastal applicability requires human review/)).toBeVisible();
    expect(screen.queryByText('NOT DETERMINED FOR REQUESTED PERIOD')).toBeNull();
    expect(screen.getByText('Provider query UTC period')).toBeVisible();
    expect(screen.getByText('Requested coordinates')).toBeVisible();
    expect(screen.getByText(/Literal screening across returned points/)).toBeVisible();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('keeps incompatible and unresolved requirements visible without evidence cards',async()=>{
    const rows=[{...row,canonical_variable:'turbidity',notes_for_evaluation:'Provider unit FNU is not comparable with permit requirement NTU'},
      {...row,condition_id:'5',canonical_variable:'dissolved_oxygen',notes_for_evaluation:'Explicit depth required'}];
    const fetch=vi.fn(async()=>({ok:true,json:async()=>({requirements:rows,evidence_groups:[]})}));vi.stubGlobal('fetch',fetch);
    render(<Environmental session={session} analysis={doc()}/>);
    await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
    await waitFor(()=>expect(screen.getAllByTestId('environment-row')).toHaveLength(2));
    await userEvent.click(screen.getAllByText('Source and retrieval notes')[0]);
    expect(screen.getByText(/Provider unit FNU is not comparable/)).toBeVisible();
    expect(screen.queryAllByTestId('evidence-card')).toHaveLength(0);
  });
  it('commits native datetime input events before constructing the UTC request', async () => {
    const fetch=vi.fn(async()=>({ok:true,json:async()=>({requirements:[row]})}));vi.stubGlobal('fetch',fetch);
    render(<Environmental session={session} analysis={doc()}/>);
    fireEvent.input(screen.getByLabelText('Planned start (UTC)'),{target:{value:'2026-10-12T12:00'}});
    fireEvent.input(screen.getByLabelText('Planned end (UTC)'),{target:{value:'2026-10-12T14:00'}});
    await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
    const body=JSON.parse(fetch.mock.calls[0][1].body);
    expect(body.start_time).toBe('2026-10-12T12:00:00Z');expect(body.end_time).toBe('2026-10-12T14:00:00Z');
  });
  it('clears fetched state on New Analysis and never adds an extraction request', async () => {
    const fetch=vi.fn(async url=>({ok:true,json:async()=>url==='/api/session'?session:url==='/api/analyze'?doc():{requirements:[{...row,notes_for_evaluation:'FETCHED-MOCK-EVIDENCE'}]}}));vi.stubGlobal('fetch',fetch);
    render(<App/>);const user=userEvent.setup();
    await user.upload(screen.getByLabelText('Upload permit PDF'),new File(['%PDF'], 'test.pdf',{type:'application/pdf'}));
    await waitFor(()=>expect(screen.getByRole('button',{name:'Analyze',exact:true})).toBeEnabled());
    await user.click(screen.getByRole('button',{name:'Analyze',exact:true}));await screen.findByText('TEST-ENV');
    expect(screen.getAllByTestId('chart')).toHaveLength(4);
    await user.click(screen.getByRole('button',{name:'Environmental Intelligence',exact:true}));
    await user.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
    await waitFor(()=>expect(fetch.mock.calls.filter(([url])=>url==='/api/environmental')).toHaveLength(1));
    await user.click(screen.getByRole('button',{name:'New Analysis'}));
    await user.click(screen.getByRole('button',{name:'Environmental Intelligence',exact:true}));
    expect(screen.queryAllByTestId('environment-row')).toHaveLength(0);
    expect(screen.queryByText('FETCHED-MOCK-EVIDENCE')).not.toBeInTheDocument();
    expect(fetch.mock.calls.filter(([url])=>url==='/api/analyze')).toHaveLength(1);
  });
});

it.each([
  ['turbidity','NTU','FNU',true],['turbidity','FNU','FNU',false],
  ['turbidity','NTU','NTU',false],['wind_speed_10m','NTU','FNU',false]
])('manual FNU visibility for %s/%s/%s',async(variable,unit,providerUnit,visible)=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  const mapped={...row,canonical_variable:variable,unit,provider_evidence_unit:providerUnit,requirement_index:0};
  render(<Environmental session={session} analysis={{...doc(),environmental_mapping:[mapped]}}/>);
  await userEvent.click(screen.getByText('Source and retrieval notes'));
  const input=screen.queryByLabelText('Manual FNU threshold · condition 4');
  if(visible){
    expect(input).toBeVisible();await userEvent.type(input,'27');
    expect(screen.getByText(/Original permit threshold:/)).toHaveTextContent('2.5 NTU');
    expect(screen.getByText(/Automatic NTU→FNU conversion is not performed/)).toBeVisible();
  }else expect(input).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
});

it('manual input is only sent on explicit Fetch and invalid values never unlock screening',async()=>{
  const mapped={...row,canonical_variable:'turbidity',unit:'NTU',threshold:25,requirement_index:0,provider_evidence_unit:'FNU'};
  const fetch=vi.fn(async()=>({ok:true,json:async()=>({requirements:[mapped],evidence_groups:[]})}));vi.stubGlobal('fetch',fetch);
  render(<Environmental session={session} analysis={{...doc(),environmental_mapping:[mapped]}}/>);
  await userEvent.click(screen.getByText('Source and retrieval notes'));
  const input=screen.getByLabelText('Manual FNU threshold · condition 4');
  fireEvent.change(input,{target:{value:'-1'}});
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
  expect(JSON.parse(fetch.mock.calls[0][1].body).manual_fnu_thresholds).toEqual({});
  await waitFor(()=>expect(screen.getByRole('button',{name:'Fetch Environmental Data'})).toBeEnabled());
  fireEvent.change(input,{target:{value:'27'}});
  expect(fetch).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
  expect(JSON.parse(fetch.mock.calls[1][1].body).manual_fnu_thresholds).toEqual({'0':27});
  expect(fetch.mock.calls.every(([url])=>url==='/api/environmental')).toBe(true);
});

it.each([
  ['Requested period not fully covered','requested period not fully covered'],
  ['Selected cell exceeds known model/grid representativeness','spatial representativeness not established'],
  ['Provider unit incompatible with permit requirement','provider unit incompatible with permit requirement'],
  ['Explicit depth required','explicit compatible depth required'],
  ['Threshold interpretation requires review','threshold interpretation requires review'],
])('shows actual blocker: %s',(note,expected)=>{
  expect(blockerLabel({evidence:{validation_notes:[note]}})).toBe(`NOT DETERMINED — ${expected}`);
});

it('distinguishes source verification from threshold interpretation blockers',()=>{
  expect(blockerLabel({notes_for_evaluation:'Source verification required before fetching'}))
    .toBe('NOT DETERMINED — source verification required');
  expect(blockerLabel({notes_for_evaluation:'Threshold interpretation requires review'}))
    .toBe('NOT DETERMINED — threshold interpretation requires review');
});
