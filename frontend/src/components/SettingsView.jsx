import React, { useState, useEffect } from 'react';
import { Save, Check, Sliders, Globe, FileText, Sparkles } from 'lucide-react';
import { updateProject } from '../api';

export default function SettingsView({
  project,
  models = [],
  presets = [],
  onRefreshProject
}) {
  const [title, setTitle] = useState(project.title);
  const [topic, setTopic] = useState(project.topic);
  const [preset, setPreset] = useState(project.preset || 'Standard Brief');
  const [directives, setDirectives] = useState(project.directives || '');
  const [model, setModel] = useState(project.model || 'openai/gpt-oss-120b');
  const [seedUrls, setSeedUrls] = useState((project.seed_urls || []).join('\n'));
  const [crawlDepth, setCrawlDepth] = useState(project.crawl_depth || 1);
  const [maxPages, setMaxPages] = useState(project.max_pages || 12);
  const [sameDomain, setSameDomain] = useState(project.same_domain ?? true);
  const [relevanceThreshold, setRelevanceThreshold] = useState(project.relevance_threshold || 6.0);
  const [topK, setTopK] = useState(project.top_k || 5);
  const [chunkSize, setChunkSize] = useState(project.chunk_size || 600);
  const [chunkOverlap, setChunkOverlap] = useState(project.chunk_overlap || 100);

  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    setTitle(project.title);
    setTopic(project.topic);
    setPreset(project.preset || 'Standard Brief');
    setDirectives(project.directives || '');
    setModel(project.model || 'openai/gpt-oss-120b');
    setSeedUrls((project.seed_urls || []).join('\n'));
    setCrawlDepth(project.crawl_depth || 1);
    setMaxPages(project.max_pages || 12);
    setSameDomain(project.same_domain ?? true);
    setRelevanceThreshold(project.relevance_threshold || 6.0);
    setTopK(project.top_k || 5);
    setChunkSize(project.chunk_size || 600);
    setChunkOverlap(project.chunk_overlap || 100);
  }, [project]);

  const handlePresetChange = (presetId) => {
    setPreset(presetId);
    const found = presets.find((p) => p.id === presetId);
    if (found && presetId !== 'Custom Directives') {
      setDirectives(found.text);
    } else if (presetId === 'Custom Directives') {
      setDirectives('');
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const urls = seedUrls
        .split('\n')
        .map((u) => u.trim())
        .filter((u) => u.length > 0);

      await updateProject(project.id, {
        title,
        topic,
        preset,
        directives,
        model,
        seed_urls: urls,
        crawl_depth: Number(crawlDepth),
        max_pages: Number(maxPages),
        same_domain: Boolean(sameDomain),
        relevance_threshold: Number(relevanceThreshold),
        top_k: Number(topK),
        chunk_size: Number(chunkSize),
        chunk_overlap: Number(chunkOverlap),
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
      onRefreshProject();
    } catch (err) {
      alert(`Failed to save settings: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form onSubmit={handleSave} className="space-y-6 max-w-4xl">
      {/* Top Banner & Save Button */}
      <div className="flex items-center justify-between bg-[#161b22] border border-[#30363d] rounded-xl p-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Project Workspace Configuration</h3>
          <p className="text-xs text-gray-400">Update model, directives, crawler boundaries and RAG parameters</p>
        </div>

        <button
          type="submit"
          disabled={isSaving}
          className="flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-4 py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
        >
          {savedSuccess ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span>Saved!</span>
            </>
          ) : isSaving ? (
            <span>Saving...</span>
          ) : (
            <>
              <Save className="w-3.5 h-3.5" />
              <span>Save Configuration</span>
            </>
          )}
        </button>
      </div>

      {/* Main Settings Card */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-6 space-y-5">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
            Project Title
          </label>
          <input
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
            Research Topic / Subject
          </label>
          <input
            type="text"
            required
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
              Synthesis LLM Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            >
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
              Instruction Preset
            </label>
            <select
              value={preset}
              onChange={(e) => handlePresetChange(e.target.value)}
              className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            >
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
            Report Directives & Custom Instructions
          </label>
          <textarea
            rows={3}
            value={directives}
            onChange={(e) => setDirectives(e.target.value)}
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
            Seed Crawl URLs (one per line)
          </label>
          <textarea
            rows={2}
            value={seedUrls}
            onChange={(e) => setSeedUrls(e.target.value)}
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm font-mono text-gray-200 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Advanced Crawler & RAG Parameters Card */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-6 space-y-6">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 flex items-center space-x-1.5">
          <Sliders className="w-4 h-4" />
          <span>Crawler & Vector Indexing Controls</span>
        </h4>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-xs">
          <div>
            <div className="flex justify-between text-gray-300 mb-1">
              <span>Max Crawl Depth</span>
              <strong className="font-mono text-indigo-400">{crawlDepth}</strong>
            </div>
            <input
              type="range"
              min={1}
              max={3}
              value={crawlDepth}
              onChange={(e) => setCrawlDepth(e.target.value)}
              className="w-full accent-indigo-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-gray-300 mb-1">
              <span>Max Discovered Pages</span>
              <strong className="font-mono text-indigo-400">{maxPages}</strong>
            </div>
            <input
              type="range"
              min={5}
              max={25}
              value={maxPages}
              onChange={(e) => setMaxPages(e.target.value)}
              className="w-full accent-indigo-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-gray-300 mb-1">
              <span>LLM Filter Threshold (0 - 10)</span>
              <strong className="font-mono text-indigo-400">{relevanceThreshold}</strong>
            </div>
            <input
              type="range"
              min={1}
              max={10}
              step={0.5}
              value={relevanceThreshold}
              onChange={(e) => setRelevanceThreshold(e.target.value)}
              className="w-full accent-indigo-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-gray-300 mb-1">
              <span>Top-K Retrieved Chunks</span>
              <strong className="font-mono text-indigo-400">{topK}</strong>
            </div>
            <input
              type="range"
              min={3}
              max={10}
              value={topK}
              onChange={(e) => setTopK(e.target.value)}
              className="w-full accent-indigo-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-gray-300 mb-1">
              <span>Chunk Size (Tokens)</span>
              <strong className="font-mono text-indigo-400">{chunkSize}</strong>
            </div>
            <input
              type="range"
              min={300}
              max={900}
              step={50}
              value={chunkSize}
              onChange={(e) => setChunkSize(e.target.value)}
              className="w-full accent-indigo-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-gray-300 mb-1">
              <span>Chunk Overlap (Tokens)</span>
              <strong className="font-mono text-indigo-400">{chunkOverlap}</strong>
            </div>
            <input
              type="range"
              min={50}
              max={200}
              step={25}
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(e.target.value)}
              className="w-full accent-indigo-500"
            />
          </div>
        </div>

        <div className="flex items-center space-x-2 pt-2 border-t border-[#30363d]/60 text-xs">
          <input
            type="checkbox"
            id="sameDomainToggle"
            checked={sameDomain}
            onChange={(e) => setSameDomain(e.target.checked)}
            className="rounded bg-[#0d1117] border-[#30363d] text-indigo-500 focus:ring-0 cursor-pointer"
          />
          <label htmlFor="sameDomainToggle" className="text-gray-300 cursor-pointer select-none">
            Strict Same Domain restriction (confines web crawler exclusively to the hostnames of seed URLs)
          </label>
        </div>
      </div>
    </form>
  );
}
