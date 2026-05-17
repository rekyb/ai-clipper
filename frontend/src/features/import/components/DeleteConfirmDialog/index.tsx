'use client';

import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from '@mui/material';

import { highSurface } from '@/features/import/lib/surfaces';

export function DeleteConfirmDialog({
  open,
  title,
  onCancel,
  onConfirm,
  isDeleting,
}: {
  open: boolean;
  title: string;
  onCancel: () => void;
  onConfirm: () => void;
  isDeleting: boolean;
}) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      maxWidth="sm"
      fullWidth
      slotProps={{ paper: { sx: { ...highSurface, p: 0 } } }}
    >
      <DialogTitle>Delete &quot;{title}&quot;?</DialogTitle>
      <DialogContent>
        <DialogContentText>
          This removes the source file from your disk. This cannot be undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} color="inherit" autoFocus disabled={isDeleting}>
          Cancel
        </Button>
        <Button onClick={onConfirm} color="error" variant="contained" disabled={isDeleting}>
          {isDeleting ? 'Deleting…' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
