/* eslint-disable @typescript-eslint/no-empty-interface, @typescript-eslint/no-explicit-any */
/**
 * Auto-generated from Pydantic schemas via backend/scripts/generate_ts.py.
 * Re-run the script after updating Pydantic models; do not edit by hand.
 */

export type VideoSource = "upload" | "youtube";
export type VideoStatus = "uploading" | "imported" | "queued" | "transcribing" | "ready" | "failed";

export interface UrlImportRequest {
  url: string;
}
export interface VideoDocument {
  id: string;
  filename: string;
  title: string;
  source: VideoSource;
  sourceUrl?: string | null;
  storagePath: string;
  thumbnailPath?: string | null;
  durationSec?: number | null;
  fileSizeBytes: number;
  container?: string | null;
  contentHash?: string | null;
  status: VideoStatus;
  errorCode?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
  lastProgressPercent?: number | null;
  transcriptionStartedAt?: string | null;
  transcriptionFinishedAt?: string | null;
  restartedAt?: string | null;
}
export interface VideoListResponse {
  videos: VideoDocument[];
}
