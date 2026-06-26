import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;

export const auth = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
};

export const cameras = {
  list: () => api.get('/cameras'),
  get: (id) => api.get(`/cameras/${id}`),
  create: (data) => api.post('/cameras', data),
  update: (id, data) => api.patch(`/cameras/${id}`, data),
  delete: (id) => api.delete(`/cameras/${id}`),
  test: (id) => api.post(`/cameras/${id}/test`, {}, { timeout: 20000 }),
  snapshot: (id) => api.post(`/cameras/${id}/snapshot`, {}, { timeout: 20000 }),
  liveSnapshot: async (id) => {
    const res = await api.get(`/cameras/${id}/snapshot/live`, {
      responseType: 'blob',
      timeout: 20000,
    });
    return res.data;
  },
  /** Abre snapshot en nueva pestaña con autenticación */
  openSnapshot: async (id) => {
    const blob = await cameras.liveSnapshot(id);
    const url = URL.createObjectURL(blob);
    const win = window.open(url, '_blank');
    if (!win) {
      URL.revokeObjectURL(url);
      throw new Error('El navegador bloqueó la ventana emergente');
    }
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },
  /** URL blob autenticada para usar en <img> o canvas */
  snapshotBlobUrl: async (id) => {
    const blob = await cameras.liveSnapshot(id);
    return URL.createObjectURL(blob);
  },
};

export const events = {
  list: (params) => api.get('/events', { params }),
  search: (params) => api.get('/events/search', { params }),
  get: (id) => api.get(`/events/${id}`),
  update: (id, data) => api.patch(`/events/${id}`, data),
  action: (id, data) => api.post(`/events/${id}/actions`, data),
};

export const rules = {
  list: (cameraId) => api.get('/rules', { params: { camera_id: cameraId } }),
  create: (data) => api.post('/rules', data),
  update: (id, data) => api.patch(`/rules/${id}`, data),
  delete: (id) => api.delete(`/rules/${id}`),
};

export const schedules = {
  list: () => api.get('/schedules'),
  create: (data) => api.post('/schedules', data),
};

export const health = {
  check: () => api.get('/health'),
  system: () => api.get('/system/health'),
};

export const integrations = {
  list: () => api.get('/integrations'),
  create: (data) => api.post('/integrations', data),
};

export const correlations = {
  list: (params) => api.get('/correlations', { params }),
};

export const llm = {
  getConfig: () => api.get('/ai/llm/config'),
  updateConfig: (data) => api.put('/ai/llm/config', data),
  testConnection: () => api.post('/ai/llm/test'),
  analyzeEvent: (eventId) => api.post(`/ai/llm/events/${eventId}/analyze`, null, { timeout: 120000 }),
  analyzeCameraImage: (cameraId) =>
    api.post('/ai/llm/analyze-image', null, { params: { camera_id: cameraId }, timeout: 120000 }),
};

export function createEventWebSocket(onMessage) {
  const wsUrl = import.meta.env.VITE_WS_URL || '/ws';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${window.location.host}${wsUrl}/events`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error('WebSocket parse error:', e);
    }
  };

  ws.onopen = () => {
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 30000);
    ws._pingInterval = ping;
  };

  ws.onclose = () => {
    if (ws._pingInterval) clearInterval(ws._pingInterval);
  };

  return ws;
}
