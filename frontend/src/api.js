const API_BASE = '/api';

// --- Authentication Token Helpers ---
const TOKEN_KEY = 'research_lens_token';

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function removeAuthToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// Wrapper for fetch that automatically attaches JWT Authorization header
async function authFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Set default Content-Type for JSON payloads if not uploading FormData
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, { ...options, headers });
  return response;
}

// --- Auth Endpoints ---
export async function registerUser({ username, email, password }) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Registration failed');
  }
  const data = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function loginUser({ username, password }) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid username or password');
  }
  const data = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function fetchCurrentUser() {
  const token = getAuthToken();
  if (!token) return null;

  const res = await authFetch(`${API_BASE}/auth/me`);
  if (!res.ok) {
    removeAuthToken();
    return null;
  }
  return res.json();
}

export function logoutUser() {
  removeAuthToken();
}

// --- System & Meta Endpoints ---
export async function fetchHealth() {
  const res = await authFetch(`${API_BASE}/health`);
  return res.json();
}

export async function fetchModels() {
  const res = await authFetch(`${API_BASE}/models`);
  return res.json();
}

export async function fetchEmbeddingModels() {
  const res = await authFetch(`${API_BASE}/embedding-models`);
  return res.json();
}

export async function fetchPresets() {
  const res = await authFetch(`${API_BASE}/presets`);
  return res.json();
}

// --- Project Endpoints ---
export async function fetchProjects(search = '') {
  const url = search ? `${API_BASE}/projects?search=${encodeURIComponent(search)}` : `${API_BASE}/projects`;
  const res = await authFetch(url);
  return res.json();
}

export async function createProject(data) {
  const res = await authFetch(`${API_BASE}/projects`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create project');
  }
  return res.json();
}

export async function fetchProject(projectId) {
  const res = await authFetch(`${API_BASE}/projects/${projectId}`);
  if (!res.ok) throw new Error('Project not found');
  return res.json();
}

export async function updateProject(projectId, data) {
  const res = await authFetch(`${API_BASE}/projects/${projectId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update project');
  return res.json();
}

export async function deleteProject(projectId) {
  const res = await authFetch(`${API_BASE}/projects/${projectId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete project');
  return res.json();
}

// --- Documents Endpoints ---
export async function uploadDocuments(projectId, files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  const res = await authFetch(`${API_BASE}/projects/${projectId}/documents`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to upload documents');
  return res.json();
}

export async function deleteDocument(docId) {
  const res = await authFetch(`${API_BASE}/documents/${docId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete document');
  return res.json();
}

export async function inspectChunks(docId) {
  const res = await authFetch(`${API_BASE}/documents/${docId}/chunks`);
  if (!res.ok) throw new Error('Failed to inspect chunks');
  return res.json();
}

// --- Crawler Endpoints ---
export async function runCrawl(projectId, options = {}) {
  const res = await authFetch(`${API_BASE}/projects/${projectId}/crawl`, {
    method: 'POST',
    body: JSON.stringify(options),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Crawl failed');
  }
  return res.json();
}

export async function deleteCrawledPage(pageId) {
  const res = await authFetch(`${API_BASE}/crawled-pages/${pageId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete crawled page');
  return res.json();
}

export async function clearCrawledPages(projectId) {
  const res = await authFetch(`${API_BASE}/projects/${projectId}/crawled-pages`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to clear crawled pages');
  return res.json();
}

// --- Reports & Synthesis Endpoints ---
export async function generateReport(projectId) {
  const res = await authFetch(`${API_BASE}/projects/${projectId}/generate-report`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Report synthesis failed');
  }
  return res.json();
}

export async function updateReport(reportId, data) {
  const res = await authFetch(`${API_BASE}/reports/${reportId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update report');
  return res.json();
}

export async function deleteReport(reportId) {
  const res = await authFetch(`${API_BASE}/reports/${reportId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete report');
  return res.json();
}

export function getPdfUrl(reportId) {
  return `${API_BASE}/reports/${reportId}/pdf`;
}
