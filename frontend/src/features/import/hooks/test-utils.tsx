import { ThemeProvider } from '@mui/material/styles';
import { type ReactNode } from 'react';
import { SWRConfig } from 'swr';

import { theme } from '@/lib/theme';

export function withFreshSwr({ children }: { children: ReactNode }) {
  return (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      {children}
    </SWRConfig>
  );
}

export function withThemeAndSwr({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
      </SWRConfig>
    </ThemeProvider>
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
