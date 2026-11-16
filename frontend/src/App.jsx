import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import ProjectDashboard from './components/ProjectDashboard';
import ProjectDetail from './components/ProjectDetail';
import NewProjectModal from './components/NewProjectModal';
import {
  fetchHealth,
  fetchModels,
  fetchPresets,
  fetchProjects,
  fetchProject,
  createProject,
  deleteProject
} from './api';

export default function App() {
  const [health, setHealth] = useState(null);
  const [models, setModels] = useState([]);
  const [presets, setPresets] = useState([]);
  const [projects, setProjects] = useState([]);
  const [search, setSearch] = useState('');
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [activeProject, setActiveProject] = useState(null);
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(true);

  // Initialize System Metadata
  useEffect(() => {
    async function loadMeta() {
      try {
        const [h, m, p] = await Promise.all([
          fetchHealth().catch(() => ({ has_groq_key: false })),
          fetchModels().catch(() => ({ models: ['openai/gpt-oss-120b'] })),
          fetchPresets().catch(() => []),
        ]);
        setHealth(h);
        setModels(m.models || ['openai/gpt-oss-120b']);
        setPresets(p || []);
      } catch (err) {
        console.error('Meta loading error:', err);
      }
    }
    loadMeta();
  }, []);

  // Fetch Projects List
  const loadProjects = async (searchTerm = '') => {
    setLoadingProjects(true);
    try {
      const data = await fetchProjects(searchTerm);
      setProjects(data || []);
    } catch (err) {
      console.error('Failed to load projects:', err);
    } finally {
      setLoadingProjects(false);
    }
  };

  useEffect(() => {
    loadProjects(search);
  }, [search]);

  // Load Active Project Detail
  const loadActiveProject = async (id) => {
    if (!id) {
      setActiveProject(null);
      return;
    }
    try {
      const data = await fetchProject(id);
      setActiveProject(data);
    } catch (err) {
      console.error('Failed to load project detail:', err);
      setActiveProjectId(null);
      setActiveProject(null);
    }
  };

  useEffect(() => {
    if (activeProjectId) {
      loadActiveProject(activeProjectId);
    } else {
      setActiveProject(null);
    }
  }, [activeProjectId]);

  const handleCreateProject = async (formData) => {
    const newProj = await createProject(formData);
    await loadProjects(search);
    setActiveProjectId(newProj.id);
  };

  const handleDeleteProject = async (id) => {
    await deleteProject(id);
    if (activeProjectId === id) {
      setActiveProjectId(null);
    }
    await loadProjects(search);
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-[#e6edf3] flex flex-col font-sans">
      <Navbar
        activeProject={activeProject}
        onNavigateHome={() => setActiveProjectId(null)}
        onOpenNewProjectModal={() => setIsNewModalOpen(true)}
        health={health}
      />

      <main className="flex-1">
        {activeProjectId && activeProject ? (
          <ProjectDetail
            project={activeProject}
            onNavigateHome={() => setActiveProjectId(null)}
            onRefreshProject={() => {
              loadActiveProject(activeProjectId);
              loadProjects(search);
            }}
            models={models}
            presets={presets}
          />
        ) : (
          <ProjectDashboard
            projects={projects}
            search={search}
            setSearch={setSearch}
            onSelectProject={(id) => setActiveProjectId(id)}
            onDeleteProject={handleDeleteProject}
            onOpenNewModal={() => setIsNewModalOpen(true)}
            loading={loadingProjects}
          />
        )}
      </main>

      <NewProjectModal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        onCreate={handleCreateProject}
        models={models}
        presets={presets}
      />

      <footer className="border-t border-[#30363d] py-6 px-6 text-center text-xs text-gray-500 bg-[#161b22]">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>ResearchLens RAG Platform • Fast, Grounded Academic Summarization</span>
          <span className="font-mono text-gray-400">FastAPI + SQLite + React Vite</span>
        </div>
      </footer>
    </div>
  );
}
