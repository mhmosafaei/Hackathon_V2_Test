import {it,expect} from 'vitest';
import {explicitUtc,environmentDefaults,boundedPeriod} from './environmentDefaults.js';
it('fills the actual English UTC permit dates even when validity exceeds the fetch limit',()=>{
  const dates=environmentDefaults({temporal_context:{permit_valid_from:'1 October 2026 00:00 UTC',permit_valid_until:'31 October 2028 23:59 UTC',source_verified:true}});
  expect(dates).toMatchObject({start:'2026-10-31T00:00',end:'2026-11-03T00:00',originalEnd:'2028-10-31T23:59',rangeAdjusted:true,testWindow:true,timingSource:'Configured test query window'});
});
it('prefers the stated operational period and independently preserves a missing end',()=>{
  const analysis={temporal_context:{operation_start:'2026-10-30T18:36:00Z',operation_end:null,permit_valid_from:'2026-01-01T00:00Z',permit_valid_until:'2028-12-31T23:59Z',source_verified:true}};
  expect(environmentDefaults(analysis)).toMatchObject({start:'2026-10-30T18:36',end:'',timingSource:'From permit operational dates'});
});
it('uses summary dates when extended timing fields are empty',()=>{
  expect(environmentDefaults({summary:{valid_from:'1 October 2026 00:00 UTC',valid_until:'31 October 2028 23:59 UTC',source_verified:true},temporal_context:{permit_valid_from:null}})).toMatchObject({start:'2026-10-31T00:00',end:'2026-11-03T00:00',originalEnd:'2028-10-31T23:59',rangeAdjusted:true});
});
it('normalizes explicit offsets and preserves seconds but never invents date-only times',()=>{
  expect(explicitUtc('2026-10-30T18:36:15+01:00')).toBe('2026-10-30T17:36:15');
  for (const value of ['1 October 2026','2026-10-01','31 February 2026 00:00 UTC','2026-02-30T00:00Z','2026-10-30T18:36']) expect(explicitUtc(value)).toBe('');
});

it('only clips periods exceeding 72 hours and preserves seconds across a year boundary',()=>{
  expect(boundedPeriod('2026-12-30T18:36:15','2027-01-10T10:00')).toEqual({end:'2027-01-02T18:36:15',originalEnd:'2027-01-10T10:00',rangeAdjusted:true});
  expect(boundedPeriod('2026-10-01T00:00','2026-10-04T00:00').rangeAdjusted).toBe(false);
  expect(boundedPeriod('2026-10-01T00:00','2026-10-02T00:00').end).toBe('2026-10-02T00:00');
  expect(boundedPeriod('','2026-10-02T00:00').rangeAdjusted).toBe(false);
});
