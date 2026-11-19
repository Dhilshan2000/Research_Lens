import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import ProjectDashboard from './components/ProjectDashboard';
import ProjectDetail from './components/ProjectDetail';
import NewProjectModal from './components/NewProjectModal';
import AuthModal from './components/AuthModal';
import {
  fetchHealth,
  fetchModels,
  fetchEmbeddingModels,
  fetchPresets,
  fetchProjects,
  fetchProject,
  createProject,
  deleteProject,
  fetchCurrentUser,
  logoutUser
} from './api';

export default function App() {
  const [health, setHealth] = useState(null);
  const [models, setModels] = useState([]);
  const [embeddingModels, setEmbeddingModels] = useState([]);
  const [presets, setPresets] = useState([]);
  const [projects, setProjects] = useState([]);
  const [search, setSearch] = useState('');
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [activeProject, setActiveProject] = useState(null);
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [loadingProjects, setLoadingProjects] = useState(true);

  // Initialize System Metadata & Authenticated User
  useEffect(() => {
    async function loadMeta() {
      try {
        const [h, m, em, p, user] = await Promise.all([
          fetchHealth().catch(() => ({ has_groq_key: false, embedding_model: 'BAAI/bge-small-en-v1.5' })),
          fetchModels().catch(() => ({ models: ['llama-3.3-70b-versatile'] })),
          fetchEmbeddingModels().catch(() => ({ models: ['BAAI/bge-small-en-v1.5'] })),
          fetchPresets().catch(() => []),
          fetchCurrentUser().catch(() => null),
        ]);
        setHealth(h);
        setModels(m.models || ['llama-3.3-70b-versatile']);
        setEmbeddingModels(em.models || ['BAAI/bge-small-en-v1.5']);
        setPresets(p || []);
        setCurrentUser(user);
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
  }, [search, currentUser]);

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

  const handleLogout = () => {
    logoutUser();
    setCurrentUser(null);
    loadProjects(search);
  };

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    loadProjects(search);
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-[#e6edf3] flex flex-col font-sans">
      <Navbar
        activeProject={activeProject}
        onNavigateHome={() => setActiveProjectId(null)}
        onOpenNewProjectModal={() => setIsNewModalOpen(true)}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        currentUser={currentUser}
        onLogout={handleLogout}
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
            embeddingModels={embeddingModels}
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
        embeddingModels={embeddingModels}
        presets={presets}
      />

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthSuccess={handleAuthSuccess}
      />

      <footer className="border-t border-[#30363d] py-6 px-6 text-center text-xs text-gray-500 bg-[#161b22]">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>ResearchLens RAG Platform • Fast, Grounded Academic Summarization</span>
          <span className="font-mono text-gray-400">FastAPI + MongoDB (27017) + ChromaDB + React Vite</span>
        </div>
      </footer>
    </div>
  );
}
