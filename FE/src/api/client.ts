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

export interface DraftTypeInfo {
  type_code: string;
  name: string;
  description: string;
  required_fields: string[];
  optional_fields: string[];
}

export interface DraftTaskStatus {
  task_id: string;
  status: string;
  document_type: string;
  progress_message: string;
  error_message: string;
  output_ready: boolean;
}

export interface AudioTaskResponse {
  id: string;
  filename: string;
  status: string;
  progress_message: string;
  error_message: string;
  output_ready: boolean;
  created_at: string;
}

export interface TemplateHeading {
  key: string;
  title: string;
  description: string;
  required: boolean;
}

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  doc_type: string;
  doc_type_label: string;
  headings: TemplateHeading[];
  status: string;
  error_message: string;
  created_at: string;
  updated_at: string;
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

  uploadDocument: (repoId: string, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
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

  // ── Drafting ──
  getDraftTypes: () =>
    api.get<DraftTypeInfo[]>('/draft/types').then(r => r.data),

  createDraft: (
    repoId: string,
    document_type: string,
    input_data: Record<string, any>,
    selected_document_ids: string[] = [],
  ) =>
    api.post(`/repositories/${repoId}/draft`, {
      document_type,
      input_data,
      selected_document_ids,
    }).then(r => r.data),

  editDraft: (taskId: string, instruction: string) =>
    api.post('/draft/edit/' + taskId, { instruction }).then(r => r.data),

  getDraftStatus: (taskId: string) =>
    api.get<DraftTaskStatus>(`/draft/status/${taskId}`).then(r => r.data),

  getDraftDownloadUrl: (taskId: string) =>
    `${API_BASE}/draft/download/${taskId}`,

  getDraftPreview: (taskId: string) =>
    api.get(`/draft/preview/${taskId}`, { responseType: 'text' }).then(r => r.data),

  deleteDraftTask: (taskId: string) =>
    api.delete(`/draft/tasks/${taskId}`),

  getDraftHistory: () =>
    api.get('/draft/history').then(r => r.data),

  deleteDraftHistoryTask: (taskId: string) =>
    api.delete(`/draft/history/${taskId}`),

  // ── Audio Recording To Minutes ──
  uploadAudio: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post('/audio/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },

  getAudioTasks: () =>
    api.get<AudioTaskResponse[]>('/audio/tasks').then(r => r.data),

  getAudioStatus: (taskId: string) =>
    api.get<AudioTaskResponse>(`/audio/status/${taskId}`).then(r => r.data),

  getAudioDownloadUrl: (taskId: string) =>
    `${API_BASE}/audio/download/${taskId}`,
    
  deleteAudioTask: (taskId: string) =>
    api.delete(`/audio/tasks/${taskId}`),

  // ── Custom Templates ──
  uploadTemplate: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post<TemplateInfo>('/templates/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },

  getTemplates: () =>
    api.get<TemplateInfo[]>('/templates').then(r => r.data),

  getTemplate: (id: string) =>
    api.get<TemplateInfo>(`/templates/${id}`).then(r => r.data),

  deleteTemplate: (id: string) =>
    api.delete(`/templates/${id}`),

  renameTemplate: (id: string, name: string) =>
    api.put<TemplateInfo>(`/templates/${id}`, { name }).then(r => r.data),

  getTemplateHistory: (templateId: string) =>
    api.get(`/templates/${templateId}/history`).then(r => r.data),

  deleteTemplateTask: (taskId: string) =>
    api.delete(`/templates/history/${taskId}`),

  generateFromTemplate: (
    templateId: string,
    input_data: Record<string, string>,
    repo_id: string,
    selected_document_ids: string[] = [],
  ) =>
    api.post(`/templates/${templateId}/generate`, {
      input_data,
      repo_id,
      selected_document_ids,
    }).then(r => r.data),

  getTemplateGenStatus: (taskId: string) =>
    api.get(`/templates/generate/status/${taskId}`).then(r => r.data),

  getTemplateDownloadUrl: (taskId: string) =>
    `${API_BASE}/templates/download/${taskId}`,

  getTemplatePreview: (taskId: string) =>
    api.get(`/templates/preview/${taskId}`, { responseType: 'text' }).then(r => r.data),

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
