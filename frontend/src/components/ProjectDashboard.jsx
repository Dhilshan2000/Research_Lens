import React, { useState } from 'react';
import {
  FolderGit2,
  Search,
  FileText,
  Globe,
  Layers,
  Calendar,
  Trash2,
  ArrowRight,
  Sparkles,
  Database,
  Plus
} from 'lucide-react';

export default function ProjectDashboard({
  projects,
  search,
  setSearch,
  onSelectProject,
  onDeleteProject,
  onOpenNewModal,
  loading
}) {
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

  const totalDocuments = projects.reduce((acc, p) => acc + (p.document_count || 0), 0);
  const totalReports = projects.reduce((acc, p) => acc + (p.report_count || 0), 0);
  const totalCrawled = projects.reduce((acc, p) => acc + (p.crawled_count || 0), 0);

  const handleDelete = (e, id) => {
    e.stopPropagation();
    if (deleteConfirmId === id) {
      onDeleteProject(id);
      setDeleteConfirmId(null);
    } else {
      setDeleteConfirmId(id);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Top Welcome / Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Research Projects</span>
            <FolderGit2 className="w-5 h-5 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white">{projects.length}</div>
          <p className="text-xs text-gray-500 mt-1">Active research workspaces</p>
        </div>

        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Indexed Documents</span>
            <FileText className="w-5 h-5 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white">{totalDocuments}</div>
          <p className="text-xs text-gray-500 mt-1">PDF, DOCX, CSV, XLSX, TXT</p>
        </div>

        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Web Sources Scraped</span>
            <Globe className="w-5 h-5 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white">{totalCrawled}</div>
          <p className="text-xs text-gray-500 mt-1">LLM-filtered web pages</p>
        </div>

        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Synthesized Reports</span>
            <Sparkles className="w-5 h-5 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-white">{totalReports}</div>
          <p className="text-xs text-gray-500 mt-1">Publication-ready citation PDFs</p>
        </div>
      </div>

      {/* Search & Actions Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects by topic, title..."
            className="w-full bg-[#161b22] border border-[#30363d] rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <button
          onClick={onOpenNewModal}
          className="w-full sm:w-auto flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors shadow-sm cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Research Workspace</span>
        </button>
      </div>

      {/* Projects List / Grid */}
      {loading ? (
        <div className="text-center py-20">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-400">Loading research workspaces...</p>
        </div>
      ) : projects.length === 0 ? (
        <div className="bg-[#161b22] border border-[#30363d] rounded-2xl p-12 text-center max-w-xl mx-auto shadow-sm">
          <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mx-auto mb-4">
            <FolderGit2 className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">No Research Projects Found</h3>
          <p className="text-sm text-gray-400 mb-6">
            {search
              ? `No projects matching "${search}". Try clearing your search term.`
              : 'Create your first research project to upload papers, discover web evidence, and synthesize grounded research reports.'}
          </p>
          <button
            onClick={onOpenNewModal}
            className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Create Research Project</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {projects.map((proj) => (
            <div
              key={proj.id}
              onClick={() => onSelectProject(proj.id)}
              className="group bg-[#161b22] border border-[#30363d] hover:border-indigo-500/50 rounded-xl p-5 shadow-sm hover:shadow-indigo-500/10 transition-all cursor-pointer flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <h4 className="font-semibold text-white group-hover:text-indigo-400 transition-colors line-clamp-1">
                    {proj.title}
                  </h4>
                  <span className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 border border-gray-700 shrink-0">
                    {proj.preset || 'Brief'}
                  </span>
                </div>

                <p className="text-xs text-gray-400 line-clamp-2 mb-4 leading-relaxed">
                  {proj.topic}
                </p>

                <div className="flex flex-wrap gap-1.5 mb-4">
                  <span className="text-[11px] bg-[#0d1117] text-gray-400 px-2 py-0.5 rounded border border-[#30363d] font-mono">
                    {proj.model.split('/').pop()}
                  </span>
                </div>
              </div>

              <div className="pt-4 border-t border-[#30363d]/60 flex items-center justify-between text-xs text-gray-400">
                <div className="flex items-center space-x-3">
                  <div className="flex items-center space-x-1" title="Uploaded documents">
                    <FileText className="w-3.5 h-3.5 text-gray-500" />
                    <span>{proj.document_count || 0}</span>
                  </div>
                  <div className="flex items-center space-x-1" title="Crawled web pages">
                    <Globe className="w-3.5 h-3.5 text-gray-500" />
                    <span>{proj.crawled_count || 0}</span>
                  </div>
                  <div className="flex items-center space-x-1" title="Generated reports">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{proj.report_count || 0}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-1">
                  <button
                    onClick={(e) => handleDelete(e, proj.id)}
                    className={`p-1.5 rounded transition-colors ${
                      deleteConfirmId === proj.id
                        ? 'bg-rose-500/20 text-rose-400 font-semibold'
                        : 'hover:bg-gray-800 text-gray-500 hover:text-rose-400'
                    }`}
                    title={deleteConfirmId === proj.id ? 'Click again to confirm delete' : 'Delete Project'}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                  <div className="p-1.5 rounded hover:bg-gray-800 text-gray-400 group-hover:text-indigo-400 transition-colors">
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
