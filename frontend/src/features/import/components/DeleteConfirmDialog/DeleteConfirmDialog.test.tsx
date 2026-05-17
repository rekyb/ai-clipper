import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { withThemeAndSwr } from '@/features/import/hooks/test-utils';
import { DeleteConfirmDialog } from './index';

describe('DeleteConfirmDialog', () => {
  it('does not render content when closed', () => {
    render(
      <DeleteConfirmDialog
        open={false}
        title="My Video"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        isDeleting={false}
      />,
      { wrapper: withThemeAndSwr },
    );
    expect(screen.queryByText(/Delete/)).not.toBeInTheDocument();
  });

  it('renders the title and destructive copy when open', () => {
    render(
      <DeleteConfirmDialog
        open
        title="My Video"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        isDeleting={false}
      />,
      { wrapper: withThemeAndSwr },
    );
    expect(screen.getByText(/Delete "My Video"\?/)).toBeInTheDocument();
    expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
  });

  it('fires onCancel when Cancel is clicked', async () => {
    const onCancel = vi.fn();
    render(
      <DeleteConfirmDialog
        open
        title="x"
        onCancel={onCancel}
        onConfirm={vi.fn()}
        isDeleting={false}
      />,
      { wrapper: withThemeAndSwr },
    );
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalled();
  });

  it('fires onConfirm when Delete is clicked', async () => {
    const onConfirm = vi.fn();
    render(
      <DeleteConfirmDialog
        open
        title="x"
        onCancel={vi.fn()}
        onConfirm={onConfirm}
        isDeleting={false}
      />,
      { wrapper: withThemeAndSwr },
    );
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it('disables both buttons while deleting', () => {
    render(
      <DeleteConfirmDialog
        open
        title="x"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        isDeleting
      />,
      { wrapper: withThemeAndSwr },
    );
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Deleting/ })).toBeDisabled();
  });
});
