import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import { QueuePositionPill } from './';

describe('QueuePositionPill', () => {
  it('renders NEXT UP for position 1', () => {
    render(<QueuePositionPill position={1} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('queue-position-pill').textContent).toBe('NEXT UP');
  });

  it('renders 2ND IN QUEUE for position 2', () => {
    render(<QueuePositionPill position={2} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('queue-position-pill').textContent).toBe('2ND IN QUEUE');
  });

  it('renders 3RD IN QUEUE for position 3', () => {
    render(<QueuePositionPill position={3} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('queue-position-pill').textContent).toBe('3RD IN QUEUE');
  });

  it('renders 4TH IN QUEUE for position 4', () => {
    render(<QueuePositionPill position={4} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('queue-position-pill').textContent).toBe('4TH IN QUEUE');
  });

  it('renders 11TH IN QUEUE for position 11 (teen exception)', () => {
    render(<QueuePositionPill position={11} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('queue-position-pill').textContent).toBe('11TH IN QUEUE');
  });

  it('renders 22ND IN QUEUE for position 22', () => {
    render(<QueuePositionPill position={22} />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('queue-position-pill').textContent).toBe('22ND IN QUEUE');
  });

  it('renders nothing when position is null', () => {
    render(<QueuePositionPill position={null} />, { wrapper: withThemeAndSwr });
    expect(screen.queryByTestId('queue-position-pill')).toBeNull();
  });

  it('renders nothing when position is below 1', () => {
    render(<QueuePositionPill position={0} />, { wrapper: withThemeAndSwr });
    expect(screen.queryByTestId('queue-position-pill')).toBeNull();
  });
});
