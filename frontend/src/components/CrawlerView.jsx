import React, { useState } from 'react';
import {
  Globe,
  Play,
  Trash2,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { runCrawl, deleteCrawledPage, clearCrawledPages } from '../api';

export default function CrawlerView({
  project,
  crawledPages = [],
  onRefreshProject
}) {
  const [isCrawling, setIsCrawling] = useState(false);
  const [crawlStatus, setCrawlStatus] = useState('');

  const relevantCount = crawledPages.filter((p) => p.is_relevant).length;

  const handleStartCrawl = async () => {
    if (!project.seed_urls?.length) {
      alert('Please configure at least one Seed Crawl URL in project settings.');
      return;
    }

    setIsCrawling(true);
    setCrawlStatus('Executing bounded crawler & Groq LLM relevance filter...');
    try {
      const res = await runCrawl(project.id);
      setCrawlStatus(`Crawl complete! Discovered ${res.discovered_count} pages, ${res.relevant_count} approved.`);
      onRefreshProject();
    } catch (err) {
      alert(`Crawl failed: ${err.message}`);
      setCrawlStatus('');
    } finally {
      setIsCrawling(false);
    }
  };

  const handleDeletePage = async (pageId) => {
    try {
      await deleteCrawledPage(pageId);
      onRefreshProject();
    } catch (err) {
      alert(`Failed to delete crawled page: ${err.message}`);
    }
  };

  const handleClearAll = async () => {
    if (!confirm('Clear all discovered web pages for this project?')) return;
    try {
      await clearCrawledPages(project.id);
      onRefreshProject();
      setCrawlStatus('');
    } catch (err) {
      alert(`Failed to clear pages: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Controls Box */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
              <Globe className="w-4 h-4 text-indigo-400" />
              <span>Bounded Web Discovery & Relevance Filter</span>
            </h3>
            <p className="text-xs text-gray-400 mt-1">
              Crawler traverses strictly from user-specified seed URLs and evaluates each discovered page with Groq LLM.
            </p>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            {crawledPages.length > 0 && (
              <button
                onClick={handleClearAll}
                disabled={isCrawling}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white text-xs font-medium transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear Cache</span>
              </button>
            )}

            <button
              onClick={handleStartCrawl}
              disabled={isCrawling}
              className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-4 py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
            >
              {isCrawling ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Crawling & Filtering...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Run Bounded Crawl</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Crawl Settings Badges */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-[#30363d]/60 text-xs text-gray-400">
          <span className="bg-[#0d1117] px-2.5 py-1 rounded border border-[#30363d]">
            Seeds: <strong className="text-gray-200">{project.seed_urls?.length || 0}</strong>
          </span>
          <span className="bg-[#0d1117] px-2.5 py-1 rounded border border-[#30363d]">
            Max Depth: <strong className="text-gray-200">{project.crawl_depth}</strong>
          </span>
          <span className="bg-[#0d1117] px-2.5 py-1 rounded border border-[#30363d]">
            Max Pages: <strong className="text-gray-200">{project.max_pages}</strong>
          </span>
          <span className="bg-[#0d1117] px-2.5 py-1 rounded border border-[#30363d]">
            Filter Threshold: <strong className="text-gray-200">{project.relevance_threshold} / 10</strong>
          </span>
          <span className="bg-[#0d1117] px-2.5 py-1 rounded border border-[#30363d]">
            Strict Domain: <strong className="text-gray-200">{project.same_domain ? 'Yes' : 'No'}</strong>
          </span>
        </div>

        {crawlStatus && (
          <div className="text-xs text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-2.5">
            {crawlStatus}
          </div>
        )}
      </div>

      {/* Crawled Pages Table */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-[#30363d] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">Discovered & Filtered Pages</h3>
          <span className="text-xs text-gray-400">
            {crawledPages.length} discovered ({relevantCount} relevant)
          </span>
        </div>

        {crawledPages.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No web pages crawled yet. Click "Run Bounded Crawl" above to fetch candidate evidence.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#30363d] text-gray-400 bg-[#0d1117]">
                  <th className="py-3 px-4 font-semibold">Web Page / URL</th>
                  <th className="py-3 px-4 font-semibold">LLM Verdict</th>
                  <th className="py-3 px-4 font-semibold">Score</th>
                  <th className="py-3 px-4 font-semibold">Rejection / Relevance Reason</th>
                  <th className="py-3 px-4 font-semibold">Depth</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#30363d]/60">
                {crawledPages.map((page) => (
                  <tr key={page.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 px-4 font-medium text-white max-w-sm">
                      <div className="truncate font-semibold">{page.title || page.url}</div>
                      <a
                        href={page.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center space-x-1 text-gray-400 hover:text-indigo-400 text-[11px] truncate mt-0.5"
                      >
                        <span className="truncate">{page.url}</span>
                        <ExternalLink className="w-3 h-3 shrink-0" />
                      </a>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      {page.is_relevant ? (
                        <span className="inline-flex items-center space-x-1 text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded text-[11px] font-semibold">
                          <ShieldCheck className="w-3 h-3" />
                          <span>Relevant</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded text-[11px] font-semibold">
                          <ShieldAlert className="w-3 h-3" />
                          <span>Rejected</span>
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono font-medium text-gray-300">
                      {page.score?.toFixed(1)} / 10
                    </td>
                    <td className="py-3 px-4 text-gray-400 max-w-md text-[11px]">
                      {page.reason || '-'}
                    </td>
                    <td className="py-3 px-4 font-mono text-gray-500">
                      d={page.depth}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDeletePage(page.id)}
                        className="p-1 rounded hover:bg-rose-500/20 text-gray-400 hover:text-rose-400 transition-colors cursor-pointer"
                        title="Remove page"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
