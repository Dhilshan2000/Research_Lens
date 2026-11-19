import React, { useState } from 'react';
import {
  FileText,
  Globe,
  Sliders,
  Sparkles,
  ArrowLeft,
  RefreshCw,
  FolderOpen
} from 'lucide-react';
import ReportView from './ReportView';
import DocumentsView from './DocumentsView';
import CrawlerView from './CrawlerView';
import SettingsView from './SettingsView';
import { generateReport } from '../api';

export default function ProjectDetail({
  project,
  onNavigateHome,
  onRefreshProject,
  models = [],
  embeddingModels = [],
  presets = []
}) {
  const [activeTab, setActiveTab] = useState('reports');
  const [isGenerating, setIsGenerating] = useState(false);

  const reports = project.reports || [];
  const documents = project.documents || [];
  const crawledPages = project.crawled_pages || [];

  const handleGenerateReport = async () => {
    if (!documents.length && !crawledPages.length) {
      alert('Please upload research documents or run a crawl on seed URLs before generating a report.');
      setActiveTab('documents');
      return;
    }

    setIsGenerating(true);
    try {
      await generateReport(project.id);
      setActiveTab('reports');
      onRefreshProject();
    } catch (err) {
      alert(`Report generation failed: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
      {/* Workspace Header */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center space-x-2.5">
              <button
                onClick={onNavigateHome}
                className="p-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
                title="Back to Dashboard"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
              <h1 className="text-xl font-bold text-white tracking-tight">{project.title}</h1>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                {project.preset || 'Brief'}
              </span>
            </div>
            <p className="text-xs text-gray-400 pl-7 max-w-2xl leading-relaxed">
              <strong>Topic:</strong> {project.topic}
            </p>
          </div>

          {/* Quick Generate Action */}
          <div className="flex items-center space-x-3 shrink-0">
            <button
              onClick={handleGenerateReport}
              disabled={isGenerating}
              className="flex items-center space-x-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-md transition-all disabled:opacity-50 cursor-pointer"
            >
              {isGenerating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Synthesizing Report...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Synthesize Report</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[#30363d] mt-6 -mb-6 space-x-2 overflow-x-auto">
          <button
            onClick={() => setActiveTab('reports')}
            className={`flex items-center space-x-2 py-3 px-4 border-b-2 text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'reports'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Reports ({reports.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('documents')}
            className={`flex items-center space-x-2 py-3 px-4 border-b-2 text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'documents'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Documents ({documents.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('crawler')}
            className={`flex items-center space-x-2 py-3 px-4 border-b-2 text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'crawler'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            <span>Web Evidence ({crawledPages.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('settings')}
            className={`flex items-center space-x-2 py-3 px-4 border-b-2 text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'settings'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Configuration</span>
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="pt-2">
        {activeTab === 'reports' && (
          <ReportView
            project={project}
            reports={reports}
            onGenerateReport={handleGenerateReport}
            onRefreshProject={onRefreshProject}
            isGenerating={isGenerating}
          />
        )}

        {activeTab === 'documents' && (
          <DocumentsView
            project={project}
            documents={documents}
            onRefreshProject={onRefreshProject}
          />
        )}

        {activeTab === 'crawler' && (
          <CrawlerView
            project={project}
            crawledPages={crawledPages}
            onRefreshProject={onRefreshProject}
          />
        )}

        {activeTab === 'settings' && (
          <SettingsView
            project={project}
            models={models}
            embeddingModels={embeddingModels}
            presets={presets}
            onRefreshProject={onRefreshProject}
          />
        )}
      </div>
    </div>
  );
}
