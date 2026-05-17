/* eslint-disable @typescript-eslint/no-empty-interface, @typescript-eslint/no-explicit-any */
/**
 * Auto-generated from Pydantic schemas via backend/scripts/generate_ts.py.
 * Re-run the script after updating Pydantic models; do not edit by hand.
 */

export type VideoStatus = "uploading" | "imported" | "queued" | "transcribing" | "ready" | "failed";

export interface ProgressEvent {
  type: "snapshot" | "progress" | "complete" | "error";
  videoId: string;
  status: VideoStatus;
  percent: number;
  stage: "transcription";
  segmentsDone?: number | null;
  segmentsTotal?: number | null;
  elapsedSec: number;
  etaSec?: number | null;
  queuePosition?: number | null;
  errorCode?: string | null;
  errorMessage?: string | null;
}
export interface RetryResponse {
  id: string;
  status: VideoStatus;
}
export interface Segment {
  start: number;
  end: number;
  text: string;
  avgLogprob: number;
  noSpeechProb: number;
  words: Word[];
}
export interface Word {
  word: string;
  start: number;
  end: number;
  probability: number;
}
export interface TranscriptDocument {
  id: string;
  videoId: string;
  language: string;
  languageProbability: number;
  durationSec: number;
  modelName: string;
  modelVersion: string;
  segments: Segment[];
  createdAt: string;
}
