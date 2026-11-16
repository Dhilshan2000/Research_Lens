const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function fetchModels() {
  const res = await fetch(`${API_BASE}/models`);
  return res.json();
}

export async function fetchPresets() {
  const res = await fetch(`${API_BASE}/presets`);
  return res.json();
}

export async function fetchProjects(search = '') {
  const url = search ? `${API_BASE}/projects?search=${encodeURIComponent(search)}` : `${API_BASE}/projects`;
  const res = await fetch(url);
  return res.json();
}

export async function createProject(data) {
  const res = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create project');
  }
  return res.json();
}

export async function fetchProject(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`);
  if (!res.ok) throw new Error('Project not found');
  return res.json();
}

export async function updateProject(projectId, data) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update project');
  return res.json();
}

export async function deleteProject(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete project');
  return res.json();
}

export async function uploadDocuments(projectId, files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  const res = await fetch(`${API_BASE}/projects/${projectId}/documents`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to upload documents');
  return res.json();
}

export async function deleteDocument(docId) {
  const res = await fetch(`${API_BASE}/documents/${docId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete document');
  return res.json();
}

export async function inspectChunks(docId) {
  const res = await fetch(`${API_BASE}/documents/${docId}/chunks`);
  if (!res.ok) throw new Error('Failed to inspect chunks');
  return res.json();
}

export async function runCrawl(projectId, options = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/crawl`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Crawl failed');
  }
  return res.json();
}

export async function deleteCrawledPage(pageId) {
  const res = await fetch(`${API_BASE}/crawled-pages/${pageId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete crawled page');
  return res.json();
}

export async function clearCrawledPages(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/crawled-pages`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to clear crawled pages');
  return res.json();
}

export async function generateReport(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/generate-report`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Report synthesis failed');
  }
  return res.json();
}

export async function updateReport(reportId, data) {
  const res = await fetch(`${API_BASE}/reports/${reportId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update report');
  return res.json();
}

export async function deleteReport(reportId) {
  const res = await fetch(`${API_BASE}/reports/${reportId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete report');
  return res.json();
}

export function getPdfUrl(reportId) {
  return `${API_BASE}/reports/${reportId}/pdf`;
}
