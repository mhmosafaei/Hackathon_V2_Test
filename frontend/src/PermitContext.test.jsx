import React from 'react';
import {render,screen,fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {it,expect,vi,afterEach} from 'vitest';
import Environmental from './Environmental.jsx';

const onlineConversion = {usable:true,status:'converted',confidence:'high',wgs84:{latitude:54.108618,longitude:-6.274707},
  source_coordinate_system:'Irish Grid',source_coordinate_system_identifier:'EPSG:29903'};

const point = {location_name:'Synthetic work point',coordinates_original:'WGS84 54.1 -6.1',coordinate_system:'WGS84',
  latitude:54.1,longitude:-6.1,geometry_type:'point',source_verified:true,point_verified:true,
  source_spans:[{page:2,quotation:'WGS84 54.1 -6.1'}]};
const gridPoint={...point,coordinate_system:'IGR',coordinates_original:'IGR 312890E 319096N',
  latitude:null,longitude:null,easting:312890,northing:319096,point_verified:false};
const requirement={condition_id:'1',requirement_text:'Synthetic wind requirement',canonical_variable:'wind_speed_10m',source_spans:[],
  routing:{preferred_provider:'ECMWF_FORECAST'},status:'INSUFFICIENT_DATA'};
const base={analysis_id:'synthetic-context',filename:'fixture.pdf',summary:{},environmental_requirements:[requirement],environmental_mapping:[requirement]};
function show(extra={}) { render(<Environmental analysis={{...base,...extra}} session={{boot_id:'test'}}/>); }
afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals();});

it('converts Irish Grid only on click then copies WGS84 without further requests',async()=>{
  const fetch=vi.fn(async()=>({ok:true,json:async()=>({usable:true,status:'converted',confidence:'high',
    wgs84:{latitude:54.108618,longitude:-6.274707},source_coordinate_system:'Irish Grid',source_coordinate_system_identifier:'EPSG:29903'})}));
  vi.stubGlobal('fetch',fetch);
  show({spatial_context:[{...point,coordinate_system:'IGR',coordinates_original:'IGR 312890E 319096N',
    latitude:null,longitude:null,easting:312890,northing:319096,point_verified:false}]});
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeDisabled();
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button',{name:'Convert Coordinates'}));
  await userEvent.click(screen.getByRole('button',{name:'Use location ↓'}));
  expect(screen.getByLabelText('Latitude').valueAsNumber).toBeGreaterThan(54);
  expect(screen.getByLabelText('Longitude').valueAsNumber).toBeLessThan(-6.1);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/api/coordinates/convert');
});

it('uses an explicitly verified WGS84 point only after a click, without fetching', async()=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);show({spatial_context:[point]});
  expect(screen.getByLabelText('Latitude')).toHaveValue(null);
  await userEvent.click(screen.getByRole('button',{name:'Use location ↓'}));
  expect(screen.getByLabelText('Latitude')).toHaveValue(54.1);expect(screen.getByLabelText('Longitude')).toHaveValue(-6.1);
  expect(fetch).not.toHaveBeenCalled();
});

it.each([
  {status:'requires_review'}, {status:'failed'}, {confidence:'medium'}, {confidence:'low'},
  {wgs84:{latitude:91,longitude:-6}}, {wgs84:{latitude:null,longitude:-6}}, {wgs84:{latitude:54,longitude:190}}
])('keeps Use location disabled for an unusable online result: %j',async(change)=>{
  const fetch=vi.fn(async()=>({ok:true,json:async()=>({...onlineConversion,...change})}));vi.stubGlobal('fetch',fetch);
  show({spatial_context:[gridPoint]});
  await userEvent.click(screen.getByRole('button',{name:'Convert Coordinates'}));
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeDisabled();
  expect(screen.getByRole('alert')).toHaveTextContent('could not be verified');
  expect(screen.getByLabelText('Latitude')).toHaveValue(null);
});

it('shows safe error on API failure with no automatic retry',async()=>{
  const fetch=vi.fn(async()=>{throw new Error('network failure');});vi.stubGlobal('fetch',fetch);
  show({spatial_context:[gridPoint]});
  await userEvent.click(screen.getByRole('button',{name:'Convert Coordinates'}));
  expect(screen.getByRole('alert')).toHaveTextContent('could not be verified');
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeDisabled();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('blocks double-click dispatch while converting',async()=>{
  let resolve;const fetch=vi.fn(()=>new Promise(r=>{resolve=r;}));vi.stubGlobal('fetch',fetch);
  show({spatial_context:[gridPoint]});
  await userEvent.dblClick(screen.getByRole('button',{name:'Convert Coordinates'}));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button',{name:'Converting coordinates…'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeDisabled();
  resolve({ok:true,json:async()=>onlineConversion});
  await screen.findByRole('button',{name:'Convert Again'});
});

it('keeps independent conversions across source-location selection and rerenders',async()=>{
  const fetch=vi.fn(async()=>({ok:true,json:async()=>onlineConversion}));vi.stubGlobal('fetch',fetch);
  show({spatial_context:[gridPoint,{...gridPoint,location_name:'Second source point',coordinates_original:'IGR 300000E 300000N',easting:300000,northing:300000}]});
  const select=screen.getByLabelText('Choose a permit-defined location');
  await userEvent.selectOptions(select,'0');
  await userEvent.click(screen.getByRole('button',{name:'Convert Coordinates'}));
  await userEvent.selectOptions(select,'1');
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeDisabled();
  await userEvent.click(screen.getByRole('button',{name:'Convert Coordinates'}));
  expect(JSON.parse(fetch.mock.calls[1][1].body).location_index).toBe(1);
  await userEvent.selectOptions(select,'0');
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeEnabled();
  expect(fetch).toHaveBeenCalledTimes(2);
  await userEvent.click(screen.getByRole('button',{name:'Convert Again'}));
  expect(JSON.parse(fetch.mock.calls[2][1].body).force).toBe(true);
});
it('preserves non-WGS84 source coordinates and never inserts them into query fields',()=>{
  show({spatial_context:[{...point,coordinates_original:'IGR 123456E 234567N',coordinate_system:'Irish Grid Reference',latitude:null,longitude:null,point_verified:false}]});
  expect(screen.getByText('IGR 123456E 234567N')).toBeVisible();
  expect(screen.getByText('Coordinate conversion to WGS84 required before environmental retrieval.')).toBeVisible();
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeDisabled();expect(screen.getByLabelText('Latitude')).toHaveValue(null);
});
it('clearly displays absent coordinates and still shows context when no environmental rows exist',()=>{
  show({environmental_requirements:[],environmental_mapping:[]});
  expect(screen.getByText('Coordinates not provided in uploaded permit.')).toBeVisible();
  expect(screen.getByRole('heading',{name:'PERMIT-DEFINED LOCATION & TIME'})).toBeVisible();
});
it('labels source validity separately and never invents midnight for date-only inputs',()=>{
  show({temporal_context:{permit_valid_from:'29 March 2024',permit_valid_until:'28 March 2027',source_verified:true}});
  expect(screen.getByRole('heading',{name:'Permit validity'})).toBeVisible();
  expect(screen.getByText(/These are licence validity dates, not confirmed operational dates/)).toBeVisible();
  expect(screen.getByRole('button',{name:'Use dates ↓'})).toBeDisabled();expect(screen.getByLabelText('Planned start (UTC)')).toHaveValue('');
});
it('copies explicit UTC operation times without fetching and leaves Fetch behavior intact',async()=>{
  const fetch=vi.fn(async()=>({ok:true,json:async()=>({requirements:[]})}));vi.stubGlobal('fetch',fetch);
  show({temporal_context:{operation_start:'2026-11-02T12:00Z',operation_end:'2026-11-02T14:00Z',source_verified:true}});
  expect(screen.getByRole('heading',{name:'Planned / permitted operational period'})).toBeVisible();
  await userEvent.click(screen.getByRole('button',{name:'Use dates ↓'}));
  expect(screen.getByLabelText('Planned start (UTC)')).toHaveValue('2026-11-02T12:00');
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button',{name:'Fetch Environmental Data'}));
  expect(fetch).toHaveBeenCalledTimes(1);expect(JSON.parse(fetch.mock.calls[0][1].body).end_time).toBe('2026-11-02T14:00:00Z');
});
it('requires selection among locations and never reduces a route to its midpoint',async()=>{
  show({spatial_context:[point,{...point,location_name:'Source route',geometry_type:'route',point_verified:false}]});
  expect(screen.queryByRole('button',{name:'Use location ↓'})).toBeNull();
  await userEvent.selectOptions(screen.getByLabelText('Choose a permit-defined location'),'1');
  expect(screen.getByText('Area or route: select a confirmed point manually. No midpoint is inferred.')).toBeVisible();
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeDisabled();
  expect(screen.getByLabelText('Longitude')).toHaveValue(null);
});
it('requires source verification before date copying and places cards immediately before retrieval',()=>{
  show({temporal_context:{operation_start:'2026-11-02T12:00Z',operation_end:'2026-11-02T14:00Z',source_verified:false}});
  expect(screen.getByRole('button',{name:'Use dates ↓'})).toBeDisabled();
  const context=screen.getByRole('region',{name:'Permit-defined location and time'});
  expect(context.nextElementSibling).toHaveClass('environment-controls');
});
it('reuses existing summary validity and geofences when extended context was not extracted',()=>{
  show({summary:{valid_from:'1 April 2024',valid_until:'1 April 2027'},temporal_context:{permit_valid_from:null},
    geofences:[{name:'Existing licensed route',type:'route',coordinates_or_boundary:'Source route boundary',source_pages:[2]}]});
  expect(screen.getByText('Existing licensed route',{selector:'strong'})).toBeVisible();
  expect(screen.getByText('Start: 1 April 2024')).toBeVisible();
  expect(screen.getByRole('button',{name:'Use location ↓'})).toBeDisabled();
});
