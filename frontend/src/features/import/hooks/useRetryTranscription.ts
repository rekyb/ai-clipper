'use client';

import { useCallback, useState } from 'react';
import { useSWRConfig } from 'swr';

import { api, ApiError } from '@/lib/api';
import type { RetryResponse } from '@/lib/transcription-types';

export type UseRetryTranscription = {
  retry: (videoId: string) => Promise<RetryResponse | null>;
  isLoading: boolean;
  error: ApiError | null;
};

export function useRetryTranscription(): UseRetryTranscription {
  const { mutate } = useSWRConfig();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const retry = useCallback(
    async (videoId: string): Promise<RetryResponse | null> => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await api.post<RetryResponse>(`/api/videos/${videoId}/retry`);
        await mutate((key) => Array.isArray(key) && key[0] === 'videos');
        return result;
      } catch (e) {
        if (e instanceof ApiError) setError(e);
        else setError(new ApiError('UNKNOWN', String(e), 0));
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [mutate],
  );

  return { retry, isLoading, error };
}
