import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// ─── Auth Token Interceptor ─────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sttnb_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('sttnb_token');
      localStorage.removeItem('sttnb_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ─── Types ──────────────────────────────────────────────────────────
export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
  full_name: string;
  role: string;
  org_id?: string;
  org_name?: string;
}

export interface UserInfo {
  id: string;
  username: string;
  full_name: string;
  role: string;
  org_id?: string;
  org_name?: string;
  dept_id?: string;
  dept_name?: string;
  created_at?: string;
}

export interface Repository {
  id: string;
  name: string;
  description: string;
  notebook_id?: string;
  category_id?: string | null;
  category_name?: string | null;
  document_count: number;
  is_public: boolean;
  is_shared: boolean;
  owner_name?: string;
  created_at: string;
  updated_at: string;
}

export interface RepositoryCategory {
  id: string;
  name: string;
  description: string;
  is_public: boolean;
  is_shared: boolean;
  owner_name?: string;
  repository_count: number;
  created_at: string;
  updated_at: string;
}

export interface StorageUsage {
  used_bytes: number;
  limit_bytes: number;
  used_label: string;
  limit_label: string;
  percent: number;
}

export interface OrgInfo {
  id: string;
  name: string;
  description: string;
  max_accounts: number;
  dept_count: number;
  user_count: number;
  created_at: string;
  updated_at: string;
}

export interface DeptInfo {
  id: string;
  org_id: string;
  name: string;
  description: string;
  user_count: number;
  created_at?: string;
}

export interface AdminUser {
  id: string;
  username: string;
  full_name: string;
  role: string;
  org_id?: string;
  org_name?: string;
  dept_id?: string;
  dept_name?: string;
  ai_engine?: string | null;
  created_at?: string;
}

export interface Document {
  id: string;
  repository_id: string;
  filename: string;
  folder_key: string;
  file_size: number;
  file_type: string;
  processing_status: 'queued' | 'processing' | 'completed' | 'failed' | string;
  progress_message: string;
  error_message: string;
  chunk_count: number;
  processed_at?: string | null;
  uploaded_at: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

// ─── Auth helpers ───────────────────────────────────────────────────
export function getStoredUser(): UserInfo | null {
  const raw = localStorage.getItem('sttnb_user');
  if (raw) {
    try { return JSON.parse(raw); } catch { return null; }
  }
  return null;
}

export function getStoredToken(): string | null {
  return localStorage.getItem('sttnb_token');
}

export function setAuth(data: AuthResponse) {
  localStorage.setItem('sttnb_token', data.access_token);
  localStorage.setItem('sttnb_user', JSON.stringify({
    id: data.user_id,
    username: data.username,
    full_name: data.full_name,
    role: data.role,
    org_id: data.org_id,
    org_name: data.org_name,
  }));
}

export function clearAuth() {
  localStorage.removeItem('sttnb_token');
  localStorage.removeItem('sttnb_user');
}

// ─── API Client ─────────────────────────────────────────────────────
export const ApiClient = {
  // ── Auth ──
  login: (username: string, password: string) =>
    api.post<AuthResponse>('/auth/login', { username, password }).then(r => r.data),

  getMe: () => api.get<UserInfo>('/auth/me').then(r => r.data),

  changePassword: (data: { old_password: string; new_password: string }) =>
    api.post('/auth/change-password', data).then(r => r.data),

  // ── Repositories ──
  getRepositories: () =>
    api.get<Repository[]>('/repositories').then(r => r.data),

  createRepository: (name: string, description: string, category_id?: string) =>
    api.post<Repository>('/repositories', { name, description, category_id: category_id || null }).then(r => r.data),

  getRepositoryCategories: () =>
    api.get<RepositoryCategory[]>('/repositories/categories').then(r => r.data),

  getStorageUsage: () =>
    api.get<StorageUsage>('/repositories/storage-usage').then(r => r.data),

  createRepositoryCategory: (name: string, description: string = '', is_public: boolean = false) =>
    api.post<RepositoryCategory>('/repositories/categories', { name, description, is_public }).then(r => r.data),

  updateRepositoryCategory: (id: string, data: { name?: string; description?: string; is_public?: boolean }) =>
    api.put<RepositoryCategory>(`/repositories/categories/${id}`, data).then(r => r.data),

  deleteRepositoryCategory: (id: string) =>
    api.delete(`/repositories/categories/${id}`),

  getRepository: (id: string) =>
    api.get<Repository>(`/repositories/${id}`).then(r => r.data),

  updateRepository: (id: string, data: { name?: string; description?: string; is_public?: boolean; category_id?: string | null }) =>
    api.put<Repository>(`/repositories/${id}`, data).then(r => r.data),

  deleteRepository: (id: string) =>
    api.delete(`/repositories/${id}`),

  // ── Documents ──
  getDocuments: (repoId: string) =>
    api.get<Document[]>(`/repositories/${repoId}/documents`).then(r => r.data),

  uploadDocument: (repoId: string, file: File, folderKey: string = 'draft') => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('folder_key', folderKey);
    return api.post<Document>(`/repositories/${repoId}/documents`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },

  deleteDocument: (repoId: string, docId: string) =>
    api.delete(`/repositories/${repoId}/documents/${docId}`),

  // ── Chat (SSE) ──
  chatStream: async function* (repoId: string, message: string): AsyncGenerator<string> {
    const token = getStoredToken();
    const response = await fetch(`${API_BASE}/repositories/${repoId}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Lỗi không xác định' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') yield data.content;
            if (data.type === 'done') return;
          } catch { /* skip invalid */ }
        }
      }
    }
  },

  getChatHistory: (repoId: string) =>
    api.get(`/repositories/${repoId}/chat/history`).then(r => r.data),

  clearChatHistory: (repoId: string) =>
    api.delete(`/repositories/${repoId}/chat/history`),

  // ── Admin: Organizations ──
  getOrganizations: () =>
    api.get<OrgInfo[]>('/admin/organizations').then(r => r.data),

  createOrganization: (name: string, description: string, max_accounts: number = 0) =>
    api.post<OrgInfo>('/admin/organizations', { name, description, max_accounts }).then(r => r.data),

  updateOrganization: (id: string, data: { name?: string; description?: string; max_accounts?: number }) =>
    api.put<OrgInfo>(`/admin/organizations/${id}`, data).then(r => r.data),

  deleteOrganization: (id: string) =>
    api.delete(`/admin/organizations/${id}`),

  // ── Admin: Departments ──
  getDepartments: (orgId: string) =>
    api.get<DeptInfo[]>(`/admin/organizations/${orgId}/departments`).then(r => r.data),

  createDepartment: (orgId: string, name: string, description: string) =>
    api.post<DeptInfo>(`/admin/organizations/${orgId}/departments`, { name, description }).then(r => r.data),

  updateDepartment: (id: string, data: { name?: string; description?: string }) =>
    api.put<DeptInfo>(`/admin/departments/${id}`, data).then(r => r.data),

  deleteDepartment: (id: string) =>
    api.delete(`/admin/departments/${id}`),

  // ── Admin: Users ──
  getUsers: () =>
    api.get<AdminUser[]>('/admin/users').then(r => r.data),

  createUser: (data: { username: string; password: string; full_name: string; role: string; org_id?: string; dept_id?: string; ai_engine?: string }) =>
    api.post<AdminUser>('/admin/users', data).then(r => r.data),

  updateUser: (id: string, data: { full_name?: string; password?: string; role?: string; org_id?: string; dept_id?: string; ai_engine?: string }) =>
    api.put<AdminUser>(`/admin/users/${id}`, data).then(r => r.data),

  deleteAdminUser: (id: string) =>
    api.delete(`/admin/users/${id}`),

  // ── Health ──
  getHealth: () => api.get('/health').then(r => r.data),
};
