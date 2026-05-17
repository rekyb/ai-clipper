'use client';

import { useState } from 'react';
import { useSWRConfig } from 'swr';

import { api, ApiError } from '@/lib/api';

type DeleteResponse = { id: string; deleted: boolean };

export function useDeleteVideo() {
  const { mutate } = useSWRConfig();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const remove = async (videoId: string): Promise<boolean> => {
    setIsDeleting(true);
    setError(null);
    try {
      await api.del<DeleteResponse>(`/api/videos/${videoId}`);
      await mutate((key) => Array.isArray(key) && key[0] === 'videos');
      return true;
    } catch (e) {
      if (e instanceof ApiError) setError(e);
      else setError(new ApiError('UNKNOWN', String(e), 0));
      return false;
    } finally {
      setIsDeleting(false);
    }
  };

  return { remove, isDeleting, error };
}
