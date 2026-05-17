import { Chip } from '@mui/material';

import type { VideoStatus } from '@/features/import/types';

const VARIANTS: Record<
  VideoStatus,
  { color: 'primary' | 'secondary' | 'error'; label: string }
> = {
  uploading: { color: 'primary', label: 'Uploading' },
  imported: { color: 'secondary', label: 'Imported' },
  failed: { color: 'error', label: 'Failed' },
};

export function StatusChip({ status }: { status: VideoStatus }) {
  const v = VARIANTS[status];
  return (
    <Chip
      label={v.label}
      color={v.color}
      size="small"
      data-testid={`status-chip-${status}`}
      sx={{
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        fontWeight: 600,
        fontSize: 12,
        height: 24,
        borderRadius: 999,
      }}
    />
  );
}
