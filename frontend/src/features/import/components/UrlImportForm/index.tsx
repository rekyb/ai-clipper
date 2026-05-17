'use client';

import { Button, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';

import { useImportUrl } from '@/features/import/hooks/useImportUrl';

const YOUTUBE_HOST_RE = /^(https?:\/\/)?(www\.|m\.)?(youtube\.com|youtu\.be)\b/i;

export function UrlImportForm() {
  const { importUrl, isImporting, error, reset } = useImportUrl();
  const [url, setUrl] = useState('');
  const [hint, setHint] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setHint(null);
    if (!YOUTUBE_HOST_RE.test(url.trim())) {
      setHint('Only YouTube URLs are supported (youtube.com, youtu.be).');
      return;
    }
    reset();
    const result = await importUrl(url.trim());
    if (result) setUrl('');
  };

  return (
    <Stack component="form" onSubmit={onSubmit} spacing={1.5}>
      <TextField
        label="YouTube URL"
        placeholder="https://youtu.be/..."
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={isImporting}
        fullWidth
        size="small"
        inputProps={{ 'aria-label': 'YouTube URL' }}
      />
      <Button
        type="submit"
        variant="contained"
        color="primary"
        disabled={isImporting || url.trim().length === 0}
      >
        {isImporting ? 'Importing…' : 'Import from URL'}
      </Button>
      {hint && (
        <Typography variant="body2" color="warning.main">
          {hint}
        </Typography>
      )}
      {error && (
        <Typography variant="body2" color="error.main">
          {error.message}
        </Typography>
      )}
    </Stack>
  );
}
