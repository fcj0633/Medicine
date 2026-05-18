import axios from 'axios';

const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截器 - 自动添加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器 - 处理 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      // 不要在 /auth/ 相关请求上自动跳转，让 AuthContext 处理
      if (!url.includes('/api/auth/')) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

// ========== Auth ==========
export const authAPI = {
  register: (data) => api.post('/api/auth/register', data),
  login: (data) => api.post('/api/auth/login', data),
  getMe: () => api.get('/api/auth/me'),
};

// ========== Drugs ==========
export const drugAPI = {
  searchCatalog: (keyword, limit = 8) => api.get('/api/drugs/catalog/search', {
    params: { keyword, limit },
  }),
  createFromCatalog: (data) => api.post('/api/drugs/catalog/add', data),
  recognize: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/drugs/recognize', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  uploadAndSave: (file, targetUserId) => {
    const formData = new FormData();
    formData.append('file', file);
    if (targetUserId) formData.append('target_user_id', targetUserId);
    return api.post('/api/drugs/upload-and-save', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  create: (data) => api.post('/api/drugs/', data),
  getAll: (userId) => api.get('/api/drugs/', { params: userId ? { user_id: userId } : {} }),
  getOne: (id) => api.get(`/api/drugs/${id}`),
  update: (id, data) => api.put(`/api/drugs/${id}`, data),
  delete: (id) => api.delete(`/api/drugs/${id}`),
  getAudio: (id) => api.get(`/api/drugs/${id}/audio`),
};

// ========== Reminders ==========
export const reminderAPI = {
  autoGenerate: (drugId, targetUserId) =>
    api.post(`/api/reminders/auto-generate/${drugId}`, null, {
      params: targetUserId ? { target_user_id: targetUserId } : {},
    }),
  create: (data) => api.post('/api/reminders/', data),
  createBatch: (data) => api.post('/api/reminders/batch', data),
  getAll: (userId) => api.get('/api/reminders/', { params: userId ? { user_id: userId } : {} }),
  update: (id, data) => api.put(`/api/reminders/${id}`, data),
  delete: (id) => api.delete(`/api/reminders/${id}`),
  getAudio: (id) => api.get(`/api/reminders/${id}/audio`),
  confirmMedication: (reminderId) => api.post('/api/reminders/logs/confirm', { reminder_id: reminderId }),
  getLogs: (userId, date) => api.get('/api/reminders/logs/', { params: { user_id: userId, date } }),
  getTodayStatus: (userId) => api.get('/api/reminders/logs/today-status', { params: userId ? { user_id: userId } : {} }),
};

// ========== Family ==========
export const familyAPI = {
  bind: (data) => api.post('/api/family/bind', data),
  getMyElderly: () => api.get('/api/family/my-elderly'),
  getMyFamily: () => api.get('/api/family/my-family'),
  unbind: (elderlyId) => api.delete(`/api/family/unbind/${elderlyId}`),
};

export default api;
