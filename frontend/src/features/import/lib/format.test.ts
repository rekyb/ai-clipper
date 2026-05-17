import { describe, expect, it } from 'vitest';

import { formatBytes, formatDuration } from './format';

describe('formatDuration', () => {
  it.each([
    [0, '0:00'],
    [5, '0:05'],
    [45, '0:45'],
    [60, '1:00'],
    [125, '2:05'],
    [3599, '59:59'],
    [3600, '1:00:00'],
    [3661, '1:01:01'],
    [10800, '3:00:00'],
  ])('formatDuration(%i) -> %s', (input, expected) => {
    expect(formatDuration(input)).toBe(expected);
  });

  it('clamps negative inputs to 0:00', () => {
    expect(formatDuration(-5)).toBe('0:00');
  });

  it('handles NaN gracefully', () => {
    expect(formatDuration(Number.NaN)).toBe('0:00');
  });
});

describe('formatBytes', () => {
  it.each([
    [0, '0 B'],
    [512, '512 B'],
    [1023, '1023 B'],
    [1024, '1.0 KB'],
    [1536, '1.5 KB'],
    [10 * 1024, '10 KB'],
    [1024 * 1024, '1.0 MB'],
    [100 * 1024 * 1024, '100 MB'],
    [1024 * 1024 * 1024, '1.0 GB'],
    [5 * 1024 * 1024 * 1024, '5.0 GB'],
  ])('formatBytes(%i) -> %s', (input, expected) => {
    expect(formatBytes(input)).toBe(expected);
  });

  it('handles negative inputs', () => {
    expect(formatBytes(-100)).toBe('0 B');
  });
});
