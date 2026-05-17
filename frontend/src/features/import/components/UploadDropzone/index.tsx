'use client';

import { Box, CircularProgress, Stack, Typography } from '@mui/material';
import { UploadIcon } from 'lucide-react';
import { useRef, useState } from 'react';

import { useUploadVideo } from '@/features/import/hooks/useUploadVideo';
import { midSurface } from '@/lib/surfaces';

export function UploadDropzone() {
  const { upload, isUploading, error, reset } = useUploadVideo();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = async (file: File) => {
    reset();
    await upload(file);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFile(file);
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFile(file);
    }
    e.target.value = '';
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box
        component="button"
        type="button"
        onClick={() => inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={() => setIsDragging(false)}
        disabled={isUploading}
        aria-label="Upload a video file"
        sx={{
          ...midSurface,
          width: '100%',
          minHeight: 200,
          flex: 1,
          p: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: isUploading ? 'not-allowed' : 'pointer',
          color: 'text.secondary',
          borderStyle: 'dashed',
          borderWidth: 1,
          borderColor: isDragging ? 'primary.main' : 'divider',
          transition: 'border-color 120ms ease-out',
          '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
        }}
      >
        <Stack alignItems="center" spacing={1.5}>
          {isUploading ? (
            <>
              <CircularProgress size={24} color="primary" />
              <Typography variant="body2">Uploading…</Typography>
            </>
          ) : (
            <>
              <UploadIcon size={32} strokeWidth={1.5} />
              <Typography variant="body2">Drop a video here or click to browse</Typography>
              <Typography
                component="span"
                sx={{
                  fontFamily: 'var(--font-jetbrains-mono), ui-monospace, monospace',
                  fontSize: 12,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'text.disabled',
                }}
              >
                MP4 · MKV · MOV · AVI · WEBM · max 5 GB · 4 h
              </Typography>
            </>
          )}
        </Stack>
      </Box>
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/x-matroska,video/quicktime,video/x-msvideo,video/webm"
        onChange={onChange}
        hidden
        aria-label="Pick a video file"
      />
      {error && (
        <Typography variant="body2" color="error.main" sx={{ mt: 1 }}>
          {error.message}
        </Typography>
      )}
    </Box>
  );
}
