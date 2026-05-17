'use client';

import { useState } from 'react';
import { useSWRConfig } from 'swr';

import type { VideoDocument } from '@/features/import/types';
import { api, ApiError } from '@/lib/api';

export function useUploadVideo() {
  const { mutate } = useSWRConfig();
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const upload = async (file: File): Promise<VideoDocument | null> => {
    setIsUploading(true);
    setError(null);
    try {
      const doc = await api.upload<VideoDocument>('/api/videos/upload', file);
      await mutate((key) => Array.isArray(key) && key[0] === 'videos');
      return doc;
    } catch (e) {
      if (e instanceof ApiError) setError(e);
      else setError(new ApiError('UNKNOWN', String(e), 0));
      return null;
    } finally {
      setIsUploading(false);
    }
  };

  const reset = () => setError(null);

  return { upload, isUploading, error, reset };
}
