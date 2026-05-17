import { type ReactNode } from 'react';
import { SWRConfig } from 'swr';

export function withFreshSwr({ children }: { children: ReactNode }) {
  return (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      {children}
    </SWRConfig>
  );
}

export function mockJsonFetch(body: unknown, ok = true, status = ok ? 200 : 500): void {
  globalThis.fetch = (() =>
    Promise.resolve({
      ok,
      status,
      statusText: ok ? 'OK' : 'Error',
      json: () => Promise.resolve(body),
    } as Response)) as unknown as typeof fetch;
}
