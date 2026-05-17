'use client';

import { useState } from 'react';
import { useSWRConfig } from 'swr';

import type { VideoDocument } from '@/features/import/types';
import { api, ApiError } from '@/lib/api';

export function useImportUrl() {
  const { mutate } = useSWRConfig();
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const importUrl = async (url: string): Promise<VideoDocument | null> => {
    setIsImporting(true);
    setError(null);
    try {
      const doc = await api.post<VideoDocument>('/api/videos/download-url', { url });
      await mutate((key) => Array.isArray(key) && key[0] === 'videos');
      return doc;
    } catch (e) {
      if (e instanceof ApiError) setError(e);
      else setError(new ApiError('UNKNOWN', String(e), 0));
      return null;
    } finally {
      setIsImporting(false);
    }
  };

  const reset = () => setError(null);

  return { importUrl, isImporting, error, reset };
}
