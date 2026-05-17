import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import { StatusChip } from './index';

describe('StatusChip', () => {
  it('renders the uploading variant with the Uploading label', () => {
    render(<StatusChip status="uploading" />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-uploading')).toHaveTextContent('Uploading');
  });

  it('renders the imported variant with the Imported label', () => {
    render(<StatusChip status="imported" />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-imported')).toHaveTextContent('Imported');
  });

  it('renders the failed variant with the Failed label', () => {
    render(<StatusChip status="failed" />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-failed')).toHaveTextContent('Failed');
  });

  it('renders the queued variant with the Queued label', () => {
    render(<StatusChip status="queued" />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-queued')).toHaveTextContent('Queued');
  });

  it('renders the transcribing variant with the Transcribing label', () => {
    render(<StatusChip status="transcribing" />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-transcribing')).toHaveTextContent('Transcribing');
  });

  it('renders the ready variant with the Ready label', () => {
    render(<StatusChip status="ready" />, { wrapper: withThemeAndSwr });
    expect(screen.getByTestId('status-chip-ready')).toHaveTextContent('Ready');
  });
});
