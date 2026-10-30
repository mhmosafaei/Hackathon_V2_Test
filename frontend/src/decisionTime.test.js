import {expect,test} from 'vitest';
import {decisionTime,timelineTicks} from './decisionTime.js';

test('readable dates always use UTC and retain nonzero seconds',()=>{
  expect(decisionTime('2026-11-05T15:00:00+01:00')).toBe('05 Nov 2026 · 14:00 UTC');
  expect(decisionTime('2026-11-05T14:00:15Z')).toBe('05 Nov 2026 · 14:00:15 UTC');
  expect(decisionTime('2026-11-05T14:00')).toBe('Not available');
  expect(decisionTime('invalid')).toBe('Not available');
});

test('axis uses actual coverage end rather than assuming a full horizon',()=>{
  const ticks=timelineTicks([{start:'2026-11-05T14:00:00Z',end:'2026-11-06T14:00:00Z'}]);
  expect(ticks).toHaveLength(5);
  expect(ticks.at(-1).time).toBe('2026-11-06T14:00:00.000Z');
  expect(ticks.at(-1).position).toBe(100);
  expect(timelineTicks([])).toEqual([]);
});
