'use client';

import { useState } from 'react';
import { useSWRConfig } from 'swr';

import type { VideoListResponse } from '@/features/import/types';
import { api, ApiError } from '@/lib/api';

type DeleteResponse = { id: string; deleted: boolean };

export function useDeleteVideo() {
  const { mutate, cache } = useSWRConfig();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const remove = async (videoId: string): Promise<boolean> => {
    setIsDeleting(true);
    setError(null);

    const snapshots = new Map<unknown, VideoListResponse | undefined>();
    for (const key of cache.keys()) {
      if (!matchesVideosKey(key)) continue;
      const entry = cache.get(key)?.data as VideoListResponse | undefined;
      snapshots.set(key, entry);
      if (entry) {
        const optimistic: VideoListResponse = {
          videos: entry.videos.filter((v) => v.id !== videoId),
        };
        await mutate(key, optimistic, { revalidate: false });
      }
    }

    try {
      await api.del<DeleteResponse>(`/api/videos/${videoId}`);
      await mutate((key) => Array.isArray(key) && key[0] === 'videos');
      return true;
    } catch (e) {
      for (const [key, prev] of snapshots) {
        await mutate(key, prev, { revalidate: false });
      }
      if (e instanceof ApiError) setError(e);
      else setError(new ApiError('UNKNOWN', String(e), 0));
      return false;
    } finally {
      setIsDeleting(false);
    }
  };

  return { remove, isDeleting, error };
}

function matchesVideosKey(key: unknown): key is ['videos', string | undefined] {
  return Array.isArray(key) && key[0] === 'videos';
}
