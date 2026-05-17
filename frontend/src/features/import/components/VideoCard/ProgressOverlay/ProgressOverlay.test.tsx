import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { TranscriptionState } from '@/lib/useTranscriptionProgress';
import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import { ProgressOverlay, formatEta } from './';

function makeState(overrides: Partial<TranscriptionState> = {}): TranscriptionState {
  return {
    status: 'transcribing',
    percent: 42,
    stage: 'transcription',
    segmentsDone: 5,
    segmentsTotal: 12,
    elapsedSec: 10,
    etaSec: 18,
    queuePosition: null,
    errorCode: null,
    errorMessage: null,
    isConnected: true,
    ...overrides,
  };
}

describe('ProgressOverlay', () => {
  it('renders the current percent', () => {
    render(<ProgressOverlay progress={makeState({ percent: 73 })} />, {
      wrapper: withThemeAndSwr,
    });
    expect(screen.getByTestId('progress-percent').textContent).toBe('73%');
  });

  it('clamps percent into the 0-100 range', () => {
    render(<ProgressOverlay progress={makeState({ percent: 150 })} />, {
      wrapper: withThemeAndSwr,
    });
    expect(screen.getByTestId('progress-percent').textContent).toBe('100%');
  });

  it('renders ETA when available', () => {
    render(<ProgressOverlay progress={makeState({ etaSec: 45 })} />, {
      wrapper: withThemeAndSwr,
    });
    expect(screen.getByTestId('progress-eta').textContent).toContain('45s');
  });

  it('hides ETA when null', () => {
    render(<ProgressOverlay progress={makeState({ etaSec: null })} />, {
      wrapper: withThemeAndSwr,
    });
    expect(screen.queryByTestId('progress-eta')).toBeNull();
  });

  it('sets ARIA progressbar attributes', () => {
    render(<ProgressOverlay progress={makeState({ percent: 33 })} />, {
      wrapper: withThemeAndSwr,
    });
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('33');
    expect(bar.getAttribute('aria-valuemin')).toBe('0');
    expect(bar.getAttribute('aria-valuemax')).toBe('100');
  });
});

describe('formatEta', () => {
  it('uses seconds under a minute', () => {
    expect(formatEta(45)).toBe('45s');
  });
  it('uses minutes between one minute and one hour', () => {
    expect(formatEta(180)).toBe('3 min');
  });
  it('uses hours past one hour', () => {
    expect(formatEta(7200)).toBe('2.0 h');
  });
});
