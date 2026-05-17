import { api } from '@/lib/api';

export const swrFetcher = <T>(path: string): Promise<T> => api.get<T>(path);
