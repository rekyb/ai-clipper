import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import { ResumptionHint, isResumptionRecent } from './';

afterEach(() => vi.useRealTimers());

describe('isResumptionRecent', () => {
  it('returns true for restart within last 30s', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-17T10:00:00Z'));
    expect(isResumptionRecent('2026-05-17T09:59:50Z')).toBe(true);
  });

  it('returns false for restart older than 30s', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-17T10:00:00Z'));
    expect(isResumptionRecent('2026-05-17T09:59:00Z')).toBe(false);
  });

  it('returns false when restartedAt is null', () => {
    expect(isResumptionRecent(null)).toBe(false);
    expect(isResumptionRecent(undefined)).toBe(false);
  });

  it('returns false for malformed timestamps', () => {
    expect(isResumptionRecent('not-a-date')).toBe(false);
  });
});

describe('ResumptionHint', () => {
  it('renders the hint text and live region', () => {
    render(<ResumptionHint />, { wrapper: withThemeAndSwr });
    const el = screen.getByTestId('resumption-hint');
    expect(el.textContent).toContain('Picking up where we left off');
    expect(el.getAttribute('aria-live')).toBe('polite');
  });
});
