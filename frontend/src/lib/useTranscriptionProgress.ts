'use client';

import { useEffect, useReducer, useRef } from 'react';

import { WS_URL } from '@/lib/env';
import type { ProgressEvent, VideoStatus } from '@/lib/transcription-types';

export type TranscriptionState = {
  status: VideoStatus | null;
  percent: number;
  stage: 'transcription' | null;
  segmentsDone: number | null;
  segmentsTotal: number | null;
  elapsedSec: number;
  etaSec: number | null;
  queuePosition: number | null;
  errorCode: string | null;
  errorMessage: string | null;
  isConnected: boolean;
};

const INITIAL_STATE: TranscriptionState = {
  status: null,
  percent: 0,
  stage: null,
  segmentsDone: null,
  segmentsTotal: null,
  elapsedSec: 0,
  etaSec: null,
  queuePosition: null,
  errorCode: null,
  errorMessage: null,
  isConnected: false,
};

type Action =
  | { kind: 'event'; event: ProgressEvent }
  | { kind: 'connection'; isConnected: boolean };

function reducer(state: TranscriptionState, action: Action): TranscriptionState {
  if (action.kind === 'connection') {
    return { ...state, isConnected: action.isConnected };
  }
  const event = action.event;
  const next: TranscriptionState = {
    status: event.status,
    percent: event.percent,
    stage: event.stage,
    segmentsDone: event.segmentsDone ?? state.segmentsDone,
    segmentsTotal: event.segmentsTotal ?? state.segmentsTotal,
    elapsedSec: event.elapsedSec,
    etaSec: event.etaSec ?? null,
    queuePosition: event.queuePosition ?? null,
    errorCode: event.errorCode ?? null,
    errorMessage: event.errorMessage ?? null,
    isConnected: state.isConnected,
  };
  if (event.type === 'complete') {
    next.status = 'ready';
    next.percent = 100;
  }
  if (event.type === 'error') {
    next.status = 'failed';
  }
  return next;
}

const BACKOFF_MS = [500, 1000, 2000, 5000, 10_000];

export function useTranscriptionProgress(
  videoId: string,
  options: { enabled?: boolean } = {},
): TranscriptionState {
  const enabled = options.enabled ?? true;
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!enabled || !videoId) return;

    let cancelled = false;
    let attempt = 0;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    stoppedRef.current = false;

    function connect(): void {
      if (cancelled) return;
      const ws = new WebSocket(`${WS_URL}/ws/${videoId}`);
      socket = ws;

      ws.onopen = () => {
        attempt = 0;
        dispatch({ kind: 'connection', isConnected: true });
      };

      ws.onmessage = (e: { data: string }) => {
        try {
          const event = JSON.parse(e.data) as ProgressEvent;
          dispatch({ kind: 'event', event });
          if (event.type === 'complete' || event.type === 'error') {
            stoppedRef.current = true;
            ws.close();
          }
        } catch {
          // Ignore non-JSON or malformed messages.
        }
      };

      ws.onclose = () => {
        dispatch({ kind: 'connection', isConnected: false });
        if (cancelled || stoppedRef.current) return;
        const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
        attempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [videoId, enabled]);

  return state;
}
