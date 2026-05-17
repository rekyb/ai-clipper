/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type VideoSource = "upload" | "youtube";
export type VideoStatus = "uploading" | "imported" | "failed";

export interface UrlImportRequest {
  url: string;
}
export interface VideoDocument {
  id?: string;
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
}
export interface VideoListResponse {
  videos: VideoDocument[];
}
