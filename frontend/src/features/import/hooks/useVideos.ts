'use client';

import useSWR from 'swr';

import type { VideoDocument, VideoListResponse } from '@/features/import/types';
import { api, ApiError } from '@/lib/api';

const POLL_INTERVAL_MS = 3000;

const ACTIVE_STATES = new Set<VideoDocument['status']>([
  'uploading',
  'imported',
  'queued',
  'transcribing',
]);

const fetcher = ([, status]: ['videos', string | undefined]) => {
  const query = status ? `?status=${status}` : '';
  return api.get<VideoListResponse>(`/api/videos${query}`);
};

export function useVideos(status?: string) {
  const { data, error, isLoading, mutate } = useSWR<VideoListResponse, ApiError>(
    ['videos', status],
    fetcher,
    {
      refreshInterval: (latest) =>
        latest?.videos.some((v) => ACTIVE_STATES.has(v.status)) ? POLL_INTERVAL_MS : 0,
      revalidateOnFocus: false,
    },
  );

  const videos: VideoDocument[] = data?.videos ?? [];
  return { videos, isLoading, error, mutate };
}
