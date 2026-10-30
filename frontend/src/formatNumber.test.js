import {expect, test} from 'vitest';
import {num} from './formatNumber.js';

test('formats finite numbers for display and preserves other values',()=>{
  expect(num(0.30000000000000004)).toBe('0.3');
  expect(num(1.23456)).toBe('1.235');
  expect(num(2)).toBe('2');
  expect(num(null)).toBeNull();
  expect(num(undefined)).toBeUndefined();
  expect(num('Missing')).toBe('Missing');
  expect(num(NaN)).toBeNaN();
});
