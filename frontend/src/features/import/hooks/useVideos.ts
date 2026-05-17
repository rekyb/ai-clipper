'use client';

import useSWR from 'swr';

import type { VideoDocument, VideoStatus, VideoListResponse } from '@/features/import/types';
import { api, ApiError } from '@/lib/api';

const POLL_INTERVAL_MS = 3000;

const fetcher = ([, status]: ['videos', VideoStatus | undefined]) => {
  const query = status ? `?status=${status}` : '';
  return api.get<VideoListResponse>(`/api/videos${query}`);
};

export function useVideos(status?: VideoStatus) {
  const { data, error, isLoading, mutate } = useSWR<VideoListResponse, ApiError>(
    ['videos', status],
    fetcher,
    {
      refreshInterval: (latest) =>
        latest?.videos.some((v) => v.status === 'uploading') ? POLL_INTERVAL_MS : 0,
      revalidateOnFocus: false,
    },
  );

  const videos: VideoDocument[] = data?.videos ?? [];
  return { videos, isLoading, error, mutate };
}
