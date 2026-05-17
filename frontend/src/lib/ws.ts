import { WS_URL } from '@/lib/env';

export type WsMessage = {
  type: string;
  [key: string]: unknown;
};

export type WsHandle = {
  send: (msg: WsMessage) => void;
  close: () => void;
};

export function connectWs(jobId: string, onMessage: (msg: WsMessage) => void): WsHandle {
  const socket = new WebSocket(`${WS_URL}/ws/${jobId}`);

  socket.addEventListener('message', (event) => {
    try {
      onMessage(JSON.parse(event.data) as WsMessage);
    } catch {
      onMessage({ type: 'parse_error', raw: event.data });
    }
  });

  return {
    send: (msg) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(msg));
      }
    },
    close: () => socket.close(),
  };
}
