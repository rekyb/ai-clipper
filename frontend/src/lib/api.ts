import { API_URL } from '@/lib/env';

export type ApiEnvelope<T> = {
  data: T | null;
  error: { code: string; message: string } | null;
  meta?: Record<string, unknown>;
};

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  let body: ApiEnvelope<T>;
  try {
    body = (await response.json()) as ApiEnvelope<T>;
  } catch {
    throw new ApiError('INVALID_RESPONSE', 'Backend returned non-JSON', response.status);
  }

  if (!response.ok || body.error) {
    const err = body.error ?? { code: 'HTTP_ERROR', message: response.statusText };
    throw new ApiError(err.code, err.message, response.status);
  }

  if (body.data === null) {
    throw new ApiError('EMPTY_RESPONSE', 'Backend returned null data', response.status);
  }

  return body.data;
}

async function uploadFile<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append('file', file);
  // Browser sets the multipart boundary -- do NOT set Content-Type manually.
  const response = await fetch(`${API_URL}${path}`, { method: 'POST', body: form });

  let body: ApiEnvelope<T>;
  try {
    body = (await response.json()) as ApiEnvelope<T>;
  } catch {
    throw new ApiError('INVALID_RESPONSE', 'Backend returned non-JSON', response.status);
  }

  if (!response.ok || body.error) {
    const err = body.error ?? { code: 'HTTP_ERROR', message: response.statusText };
    throw new ApiError(err.code, err.message, response.status);
  }
  if (body.data === null) {
    throw new ApiError('EMPTY_RESPONSE', 'Backend returned null data', response.status);
  }
  return body.data;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, file: File) => uploadFile<T>(path, file),
};
