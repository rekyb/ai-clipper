'use client';

import { Button } from '@mui/material';
import { RefreshCwIcon } from 'lucide-react';

import { useRetryTranscription } from '@/features/import/hooks/useRetryTranscription';

export function RetryButton({ videoId }: Readonly<{ videoId: string }>) {
  const { retry, isLoading } = useRetryTranscription();
  return (
    <Button
      data-testid={`retry-${videoId}`}
      variant="outlined"
      size="small"
      onClick={() => {
        void retry(videoId);
      }}
      disabled={isLoading}
      startIcon={<RefreshCwIcon size={16} strokeWidth={1.75} />}
      sx={{
        borderColor: 'primary.main',
        color: 'primary.main',
        '&:hover': { borderColor: 'primary.main', bgcolor: 'rgba(157, 78, 221, 0.08)' },
      }}
    >
      Retry
    </Button>
  );
}
