import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import { StatusFilterChips } from './index';

describe('StatusFilterChips', () => {
  it('renders all six filter options', () => {
    render(<StatusFilterChips value="all" onChange={vi.fn()} />, { wrapper: withThemeAndSwr });
    for (const label of [
      'All',
      'Importing',
      'Queued',
      'Transcribing',
      'Ready',
      'Failed',
    ]) {
      expect(screen.getByRole('radio', { name: label })).toBeInTheDocument();
    }
  });

  it('marks the selected chip with aria-checked', () => {
    render(<StatusFilterChips value="queued" onChange={vi.fn()} />, {
      wrapper: withThemeAndSwr,
    });
    expect(screen.getByRole('radio', { name: 'Queued' })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('radio', { name: 'All' })).toHaveAttribute('aria-checked', 'false');
  });

  it('calls onChange with the new value when a chip is clicked', async () => {
    const onChange = vi.fn();
    render(<StatusFilterChips value="all" onChange={onChange} />, {
      wrapper: withThemeAndSwr,
    });
    await userEvent.click(screen.getByRole('radio', { name: 'Importing' }));
    expect(onChange).toHaveBeenCalledWith('importing');
  });

  it('calls onChange with transcribing when that chip is clicked', async () => {
    const onChange = vi.fn();
    render(<StatusFilterChips value="all" onChange={onChange} />, {
      wrapper: withThemeAndSwr,
    });
    await userEvent.click(screen.getByRole('radio', { name: 'Transcribing' }));
    expect(onChange).toHaveBeenCalledWith('transcribing');
  });
});
