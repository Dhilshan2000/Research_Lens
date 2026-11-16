import React from 'react';
import { Microscope, Plus, Sparkles, CheckCircle, AlertCircle, ArrowLeft } from 'lucide-react';

export default function Navbar({
  activeProject,
  onNavigateHome,
  onOpenNewProjectModal,
  health,
}) {
  return (
    <header className="border-b border-[#30363d] bg-[#161b22] sticky top-0 z-40 px-6 py-3.5 shadow-md">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand & Breadcrumbs */}
        <div className="flex items-center space-x-4">
          <div
            onClick={onNavigateHome}
            className="flex items-center space-x-2.5 cursor-pointer group"
          >
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-lg group-hover:scale-105 transition-transform">
              <Microscope className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg text-white tracking-tight">ResearchLens</span>
                <span className="text-[10px] uppercase font-semibold bg-indigo-500/20 text-indigo-400 px-1.5 py-0.5 rounded border border-indigo-500/30">
                  RAG CRUD
                </span>
              </div>
              <p className="text-xs text-gray-400 hidden sm:block">
                AI Research Summarizer & Evidence Engine
              </p>
            </div>
          </div>

          {activeProject && (
            <div className="hidden md:flex items-center space-x-2 text-sm text-gray-400 pl-4 border-l border-[#30363d]">
              <button
                onClick={onNavigateHome}
                className="hover:text-white flex items-center space-x-1 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Dashboard</span>
              </button>
              <span>/</span>
              <span className="text-gray-200 font-medium truncate max-w-[220px]">
                {activeProject.title}
              </span>
            </div>
          )}
        </div>

        {/* Right Actions */}
        <div className="flex items-center space-x-3">
          {/* Health / Groq Key Indicator */}
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#0d1117] border border-[#30363d] text-xs">
            {health?.has_groq_key ? (
              <>
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-gray-300 hidden sm:inline">Groq API:</span>
                <span className="text-emerald-400 font-medium">Connected</span>
              </>
            ) : (
              <>
                <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-amber-400 font-medium">Local Mode</span>
              </>
            )}
          </div>

          {/* New Project CTA */}
          <button
            onClick={onOpenNewProjectModal}
            className="flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-3.5 py-1.5 rounded-lg transition-colors shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>New Project</span>
          </button>
        </div>
      </div>
    </header>
  );
}
