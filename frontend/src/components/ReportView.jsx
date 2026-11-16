import React, { useState } from 'react';
import {
  FileText,
  Download,
  Trash2,
  Edit3,
  Check,
  X,
  Sparkles,
  ExternalLink,
  Table,
  AlertTriangle,
  BookmarkCheck,
  Play
} from 'lucide-react';
import { getPdfUrl, updateReport, deleteReport } from '../api';

export default function ReportView({
  project,
  reports = [],
  onGenerateReport,
  onRefreshProject,
  isGenerating,
}) {
  const [selectedReportId, setSelectedReportId] = useState(reports[0]?.id || null);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editSummary, setEditSummary] = useState('');
  const [editSynthesis, setEditSynthesis] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const activeReport = reports.find((r) => r.id === selectedReportId) || reports[0];

  const handleStartEdit = () => {
    if (!activeReport) return;
    setEditTitle(activeReport.title);
    setEditSummary(activeReport.executive_summary || '');
    setEditSynthesis(activeReport.detailed_synthesis || '');
    setIsEditing(true);
  };

  const handleSaveEdit = async () => {
    if (!activeReport) return;
    setIsSaving(true);
    try {
      await updateReport(activeReport.id, {
        title: editTitle,
        executive_summary: editSummary,
        detailed_synthesis: editSynthesis,
      });
      setIsEditing(false);
      onRefreshProject();
    } catch (err) {
      alert(`Failed to save report: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteReport = async (reportId) => {
    if (!confirm('Are you sure you want to delete this research report?')) return;
    try {
      await deleteReport(reportId);
      onRefreshProject();
      if (selectedReportId === reportId) {
        setSelectedReportId(null);
      }
    } catch (err) {
      alert(`Failed to delete report: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#161b22] border border-[#30363d] rounded-xl p-4">
        <div>
          <h3 className="text-base font-semibold text-white">Synthesis Research Reports</h3>
          <p className="text-xs text-gray-400">
            {reports.length} report(s) generated for "{project.title}"
          </p>
        </div>

        <button
          onClick={onGenerateReport}
          disabled={isGenerating}
          className="flex items-center justify-center space-x-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-all shadow-md disabled:opacity-50 cursor-pointer"
        >
          {isGenerating ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Synthesizing RAG Report...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Generate New Report</span>
            </>
          )}
        </button>
      </div>

      {reports.length === 0 ? (
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-12 text-center">
          <Sparkles className="w-12 h-12 text-indigo-400 mx-auto mb-3 opacity-60" />
          <h4 className="text-base font-medium text-white mb-1">No Reports Generated Yet</h4>
          <p className="text-xs text-gray-400 max-w-md mx-auto mb-6">
            Upload your research papers in the Documents tab or run a web crawl, then click "Generate New Report" to produce an evidence-grounded publication report.
          </p>
          <button
            onClick={onGenerateReport}
            disabled={isGenerating}
            className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors cursor-pointer"
          >
            <Play className="w-4 h-4" />
            <span>Generate First Report</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Reports Sidebar Selector */}
          <div className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 block px-1">
              Report History
            </span>
            <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1">
              {reports.map((rep) => {
                const isSelected = (activeReport?.id === rep.id);
                return (
                  <div
                    key={rep.id}
                    onClick={() => {
                      setSelectedReportId(rep.id);
                      setIsEditing(false);
                    }}
                    className={`p-3 rounded-lg border text-left cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-indigo-600/15 border-indigo-500/60 text-white'
                        : 'bg-[#161b22] border-[#30363d] text-gray-300 hover:border-gray-500'
                    }`}
                  >
                    <div className="font-medium text-xs line-clamp-1">{rep.title}</div>
                    <div className="flex items-center justify-between text-[11px] text-gray-400 mt-2">
                      <span>{new Date(rep.created_at).toLocaleDateString()}</span>
                      <span className="font-mono text-[10px] bg-[#0d1117] px-1.5 py-0.5 rounded border border-[#30363d]">
                        {rep.model_used?.split('/').pop() || 'Groq'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Active Report Main View */}
          {activeReport && (
            <div className="lg:col-span-3 space-y-6">
              {/* Report Header & Toolbar */}
              <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#30363d] pb-4">
                  {isEditing ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-1.5 text-base font-bold text-white focus:outline-none focus:border-indigo-500"
                    />
                  ) : (
                    <div>
                      <h2 className="text-lg font-bold text-white leading-tight">
                        {activeReport.title}
                      </h2>
                      <p className="text-xs text-gray-400 mt-1 flex items-center space-x-2">
                        <span>Generated: {new Date(activeReport.created_at).toLocaleString()}</span>
                        <span>•</span>
                        <span className="font-mono">{activeReport.model_used}</span>
                      </p>
                    </div>
                  )}

                  {/* Actions (PDF download, Edit, Delete) */}
                  <div className="flex items-center space-x-2 shrink-0">
                    {isEditing ? (
                      <>
                        <button
                          onClick={handleSaveEdit}
                          disabled={isSaving}
                          className="flex items-center space-x-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Save</span>
                        </button>
                        <button
                          onClick={() => setIsEditing(false)}
                          className="flex items-center space-x-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Cancel</span>
                        </button>
                      </>
                    ) : (
                      <>
                        <a
                          href={getPdfUrl(activeReport.id)}
                          download
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3.5 py-1.5 rounded-lg transition-colors shadow-sm cursor-pointer"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Download PDF</span>
                        </a>
                        <button
                          onClick={handleStartEdit}
                          className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors"
                          title="Edit Report In-place"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteReport(activeReport.id)}
                          className="p-1.5 rounded-lg bg-gray-800 hover:bg-rose-500/20 text-gray-400 hover:text-rose-400 transition-colors"
                          title="Delete Report"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Executive Summary */}
                <div className="pt-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-2 flex items-center space-x-1.5">
                    <BookmarkCheck className="w-4 h-4" />
                    <span>Executive Summary</span>
                  </h4>
                  {isEditing ? (
                    <textarea
                      rows={4}
                      value={editSummary}
                      onChange={(e) => setEditSummary(e.target.value)}
                      className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
                    />
                  ) : (
                    <div className="text-sm text-gray-300 leading-relaxed bg-[#0d1117] border border-[#30363d]/60 rounded-lg p-4">
                      {activeReport.executive_summary}
                    </div>
                  )}
                </div>

                {/* Detailed Synthesis */}
                <div className="pt-6">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-2 flex items-center space-x-1.5">
                    <FileText className="w-4 h-4" />
                    <span>Detailed Evidence Synthesis</span>
                  </h4>
                  {isEditing ? (
                    <textarea
                      rows={8}
                      value={editSynthesis}
                      onChange={(e) => setEditSynthesis(e.target.value)}
                      className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm text-gray-200 font-mono focus:outline-none focus:border-indigo-500"
                    />
                  ) : (
                    <div className="text-sm text-gray-300 leading-relaxed bg-[#0d1117] border border-[#30363d]/60 rounded-lg p-4 whitespace-pre-wrap font-sans">
                      {activeReport.detailed_synthesis}
                    </div>
                  )}
                </div>
              </div>

              {/* Comparison Table */}
              {activeReport.comparison_table?.length > 0 && (
                <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5 overflow-hidden">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-3 flex items-center space-x-1.5">
                    <Table className="w-4 h-4" />
                    <span>Comparative Architecture & Benchmark Matrix</span>
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#30363d] text-gray-400 bg-[#0d1117]">
                          <th className="py-2.5 px-3 font-semibold">Approach / System</th>
                          <th className="py-2.5 px-3 font-semibold">Dataset / Scope</th>
                          <th className="py-2.5 px-3 font-semibold">Metrics & Results</th>
                          <th className="py-2.5 px-3 font-semibold">Architecture Details</th>
                          <th className="py-2.5 px-3 font-semibold">Limitations / Gaps</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#30363d]/60">
                        {activeReport.comparison_table.map((row, idx) => (
                          <tr key={idx} className="hover:bg-white/[0.02]">
                            <td className="py-2.5 px-3 font-semibold text-white whitespace-nowrap">
                              {row.approach || row.system || `Item ${idx + 1}`}
                            </td>
                            <td className="py-2.5 px-3 text-gray-300">{row.dataset || '-'}</td>
                            <td className="py-2.5 px-3 text-emerald-400 font-mono">{row.metrics || '-'}</td>
                            <td className="py-2.5 px-3 text-gray-300">{row.architecture || '-'}</td>
                            <td className="py-2.5 px-3 text-amber-300">{row.limitations || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Research Gaps */}
              {activeReport.research_gaps?.length > 0 && (
                <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-400 mb-3 flex items-center space-x-1.5">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Identified Critical Research Gaps</span>
                  </h4>
                  <ul className="space-y-2">
                    {activeReport.research_gaps.map((gap, idx) => (
                      <li
                        key={idx}
                        className="text-xs text-gray-300 bg-[#0d1117] border border-[#30363d]/60 rounded-lg p-3 flex items-start space-x-2"
                      >
                        <span className="text-amber-400 font-bold shrink-0">•</span>
                        <span>{gap}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Citations & Evidence Provenance */}
              {activeReport.citations?.length > 0 && (
                <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3 flex items-center space-x-1.5">
                    <BookmarkCheck className="w-4 h-4 text-indigo-400" />
                    <span>Evidence Citations & Source Provenance</span>
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {activeReport.citations.map((cite, idx) => (
                      <div
                        key={idx}
                        className="bg-[#0d1117] border border-[#30363d]/60 rounded-lg p-3 text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-white truncate max-w-[200px]">
                            {cite.title || cite.source || `Citation [${idx + 1}]`}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                            {cite.source_type || 'source'}
                          </span>
                        </div>

                        {cite.page && (
                          <div className="text-gray-400 text-[11px]">
                            Page: {cite.page} {cite.section && `• Section: ${cite.section}`}
                          </div>
                        )}

                        {cite.url && (
                          <a
                            href={cite.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center space-x-1 text-indigo-400 hover:text-indigo-300 text-[11px] truncate max-w-full"
                          >
                            <span className="truncate">{cite.url}</span>
                            <ExternalLink className="w-3 h-3 shrink-0" />
                          </a>
                        )}

                        {cite.snippet && (
                          <p className="text-gray-400 text-[11px] italic line-clamp-2 mt-1">
                            "{cite.snippet}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
