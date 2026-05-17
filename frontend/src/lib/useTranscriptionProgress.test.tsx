import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ProgressEvent } from '@/lib/transcription-types';
import { useTranscriptionProgress } from '@/lib/useTranscriptionProgress';

type SocketListener = (ev: { data: string }) => void;

class FakeSocket {
  static instances: FakeSocket[] = [];
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: SocketListener | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }

  triggerOpen(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  triggerMessage(payload: object): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  triggerClose(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }
}

const snapshot = (overrides: Partial<ProgressEvent> = {}): ProgressEvent => ({
  type: 'snapshot',
  videoId: 'vid-1',
  status: 'transcribing',
  percent: 42,
  stage: 'transcription',
  elapsedSec: 12,
  segmentsDone: 3,
  segmentsTotal: 7,
  etaSec: 18,
  queuePosition: null,
  errorCode: null,
  errorMessage: null,
  ...overrides,
});

beforeEach(() => {
  FakeSocket.instances = [];
  vi.stubGlobal('WebSocket', FakeSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('useTranscriptionProgress', () => {
  it('opens a websocket to the configured URL', () => {
    renderHook(() => useTranscriptionProgress('vid-1'));
    expect(FakeSocket.instances).toHaveLength(1);
    expect(FakeSocket.instances[0].url).toContain('/ws/vid-1');
  });

  it('does not open when disabled', () => {
    renderHook(() => useTranscriptionProgress('vid-1', { enabled: false }));
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it('does not open when videoId is empty', () => {
    renderHook(() => useTranscriptionProgress(''));
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it('reflects snapshot event in returned state', async () => {
    const { result } = renderHook(() => useTranscriptionProgress('vid-1'));
    act(() => {
      FakeSocket.instances[0].triggerOpen();
      FakeSocket.instances[0].triggerMessage(snapshot());
    });
    await waitFor(() => expect(result.current.percent).toBe(42));
    expect(result.current.status).toBe('transcribing');
    expect(result.current.segmentsDone).toBe(3);
    expect(result.current.etaSec).toBe(18);
    expect(result.current.isConnected).toBe(true);
  });

  it('merges subsequent progress events into state', async () => {
    const { result } = renderHook(() => useTranscriptionProgress('vid-1'));
    act(() => {
      FakeSocket.instances[0].triggerOpen();
      FakeSocket.instances[0].triggerMessage(snapshot({ percent: 10, etaSec: 30 }));
      FakeSocket.instances[0].triggerMessage(
        snapshot({ type: 'progress', percent: 55, etaSec: 12, segmentsDone: 5 }),
      );
    });
    await waitFor(() => expect(result.current.percent).toBe(55));
    expect(result.current.etaSec).toBe(12);
    expect(result.current.segmentsDone).toBe(5);
  });

  it('flips to ready+100 on complete and closes the socket', async () => {
    const { result } = renderHook(() => useTranscriptionProgress('vid-1'));
    act(() => {
      FakeSocket.instances[0].triggerOpen();
      FakeSocket.instances[0].triggerMessage(snapshot());
      FakeSocket.instances[0].triggerMessage(
        snapshot({ type: 'complete', status: 'ready', percent: 100 }),
      );
    });
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.percent).toBe(100);
    expect(result.current.isConnected).toBe(false);
  });

  it('sets errorCode/errorMessage on error event and closes', async () => {
    const { result } = renderHook(() => useTranscriptionProgress('vid-1'));
    act(() => {
      FakeSocket.instances[0].triggerOpen();
      FakeSocket.instances[0].triggerMessage(
        snapshot({
          type: 'error',
          status: 'failed',
          errorCode: 'AUDIO_DECODE_FAILED',
          errorMessage: 'bad audio',
        }),
      );
    });
    await waitFor(() => expect(result.current.errorCode).toBe('AUDIO_DECODE_FAILED'));
    expect(result.current.status).toBe('failed');
    expect(result.current.errorMessage).toBe('bad audio');
    expect(result.current.isConnected).toBe(false);
  });

  it('reconnects with backoff on unexpected close', async () => {
    vi.useFakeTimers();
    renderHook(() => useTranscriptionProgress('vid-1'));
    expect(FakeSocket.instances).toHaveLength(1);
    act(() => {
      FakeSocket.instances[0].triggerOpen();
      FakeSocket.instances[0].triggerClose();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(FakeSocket.instances).toHaveLength(2);
    act(() => {
      FakeSocket.instances[1].triggerClose();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(FakeSocket.instances).toHaveLength(3);
  });

  it('does not reconnect after complete event', async () => {
    vi.useFakeTimers();
    renderHook(() => useTranscriptionProgress('vid-1'));
    act(() => {
      FakeSocket.instances[0].triggerOpen();
      FakeSocket.instances[0].triggerMessage(
        snapshot({ type: 'complete', status: 'ready', percent: 100 }),
      );
      FakeSocket.instances[0].triggerClose();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it('does not reconnect after error event', async () => {
    vi.useFakeTimers();
    renderHook(() => useTranscriptionProgress('vid-1'));
    act(() => {
      FakeSocket.instances[0].triggerOpen();
      FakeSocket.instances[0].triggerMessage(
        snapshot({ type: 'error', status: 'failed', errorCode: 'X', errorMessage: 'x' }),
      );
      FakeSocket.instances[0].triggerClose();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it('closes the socket on unmount', () => {
    const { unmount } = renderHook(() => useTranscriptionProgress('vid-1'));
    const socket = FakeSocket.instances[0];
    unmount();
    expect(socket.readyState).toBe(3);
  });

  it('re-opens when videoId changes', () => {
    const { rerender } = renderHook(({ id }) => useTranscriptionProgress(id), {
      initialProps: { id: 'vid-1' },
    });
    expect(FakeSocket.instances).toHaveLength(1);
    rerender({ id: 'vid-2' });
    expect(FakeSocket.instances).toHaveLength(2);
    expect(FakeSocket.instances[1].url).toContain('/ws/vid-2');
  });
});
