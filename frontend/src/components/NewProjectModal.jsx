import React, { useState } from 'react';
import { X, Sparkles, Globe, Sliders, FileText, ChevronDown, ChevronUp } from 'lucide-react';

export default function NewProjectModal({
  isOpen,
  onClose,
  onCreate,
  models = [],
  embeddingModels = [],
  presets = [],
}) {
  const [title, setTitle] = useState('');
  const [topic, setTopic] = useState('Retrieval-Augmented Generation (RAG) Architecture and Gaps');
  const [preset, setPreset] = useState('Standard Brief');
  const [directives, setDirectives] = useState(
    presets.find((p) => p.id === 'Standard Brief')?.text ||
    'Focus on research gaps, use an academic tone, add a comparison table, and keep the report under four pages.'
  );
  const [model, setModel] = useState('openai/gpt-oss-120b');
  const [embeddingModel, setEmbeddingModel] = useState('BAAI/bge-small-en-v1.5');
  const [seedUrls, setSeedUrls] = useState('https://arxiv.org/abs/2312.10997');
  const [crawlDepth, setCrawlDepth] = useState(1);
  const [maxPages, setMaxPages] = useState(12);
  const [sameDomain, setSameDomain] = useState(true);
  const [relevanceThreshold, setRelevanceThreshold] = useState(6.0);
  const [topK, setTopK] = useState(5);
  const [chunkSize, setChunkSize] = useState(600);
  const [chunkOverlap, setChunkOverlap] = useState(100);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handlePresetChange = (presetId) => {
    setPreset(presetId);
    const found = presets.find((p) => p.id === presetId);
    if (found && presetId !== 'Custom Directives') {
      setDirectives(found.text);
    } else if (presetId === 'Custom Directives') {
      setDirectives('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsSubmitting(true);
    try {
      const urls = seedUrls
        .split('\n')
        .map((u) => u.trim())
        .filter((u) => u.length > 0);

      await onCreate({
        title: title.trim(),
        topic: topic.trim(),
        directives,
        preset,
        model,
        embedding_model: embeddingModel,
        seed_urls: urls,
        crawl_depth: Number(crawlDepth),
        max_pages: Number(maxPages),
        same_domain: Boolean(sameDomain),
        relevance_threshold: Number(relevanceThreshold),
        top_k: Number(topK),
        chunk_size: Number(chunkSize),
        chunk_overlap: Number(chunkOverlap),
      });
      onClose();
    } catch (err) {
      alert(`Error creating project: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#30363d] bg-[#1a202c]">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-semibold text-white">Create Research Project</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1 rounded-md transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">
          {/* Project Title */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
              Project Title *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. RAG Survey 2026: Benchmarks & Architectures"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3.5 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          {/* Research Topic */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
              Research Topic / Scope *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Graph RAG vs Modular RAG performance and latency trade-offs"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3.5 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          {/* Model Selection */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
                Synthesis LLM Model
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
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
                className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
              >
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Directives */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
              Report Directives & Instructions
            </label>
            <textarea
              rows={3}
              value={directives}
              onChange={(e) => setDirectives(e.target.value)}
              placeholder="Specify requirements, tone, sections, or comparison parameters..."
              className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
            />
          </div>

          {/* Seed URLs */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-1.5 flex items-center justify-between">
              <span>Seed Crawl URLs (one per line)</span>
              <span className="text-[11px] text-gray-500 lowercase font-normal">Bounded Discovery</span>
            </label>
            <textarea
              rows={2}
              value={seedUrls}
              onChange={(e) => setSeedUrls(e.target.value)}
              placeholder="https://arxiv.org/abs/2312.10997"
              className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm font-mono text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
            />
          </div>

          {/* Advanced Crawler & RAG Collapsible */}
          <div className="border border-[#30363d] rounded-lg overflow-hidden bg-[#0d1117]/50">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full px-4 py-2.5 flex items-center justify-between text-xs font-semibold text-gray-400 hover:text-white transition-colors"
            >
              <div className="flex items-center space-x-2">
                <Sliders className="w-3.5 h-3.5" />
                <span>Crawler & RAG Advanced Controls</span>
              </div>
              {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showAdvanced && (
              <div className="p-4 border-t border-[#30363d] space-y-4 text-xs">
                <div>
                  <label className="text-gray-300 block mb-1 font-medium">Embedding Model (ChromaDB Vector Store)</label>
                  <select
                    value={embeddingModel}
                    onChange={(e) => setEmbeddingModel(e.target.value)}
                    className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-2 text-white font-mono text-xs focus:outline-none focus:border-indigo-500"
                  >
                    {(embeddingModels.length > 0 ? embeddingModels : ['BAAI/bge-small-en-v1.5', 'all-MiniLM-L6-v2', 'all-mpnet-base-v2', 'nomic-ai/nomic-embed-text-v1.5']).map((em) => (
                      <option key={em} value={em}>
                        {em}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-gray-400 block mb-1">Max Depth: {crawlDepth}</label>
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
                    <label className="text-gray-400 block mb-1">Max Discovered Pages: {maxPages}</label>
                    <input
                      type="range"
                      min={5}
                      max={25}
                      value={maxPages}
                      onChange={(e) => setMaxPages(e.target.value)}
                      className="w-full accent-indigo-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-gray-400 block mb-1">Filter Threshold: {relevanceThreshold}</label>
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
                    <label className="text-gray-400 block mb-1">Top-K Chunks: {topK}</label>
                    <input
                      type="range"
                      min={3}
                      max={10}
                      value={topK}
                      onChange={(e) => setTopK(e.target.value)}
                      className="w-full accent-indigo-500"
                    />
                  </div>
                </div>

                <div className="flex items-center space-x-2 pt-1">
                  <input
                    type="checkbox"
                    id="sameDomainCheck"
                    checked={sameDomain}
                    onChange={(e) => setSameDomain(e.target.checked)}
                    className="rounded bg-[#0d1117] border-[#30363d] text-indigo-500 focus:ring-0 cursor-pointer"
                  />
                  <label htmlFor="sameDomainCheck" className="text-gray-300 cursor-pointer select-none">
                    Strict Same Domain crawling restriction
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end space-x-3 pt-3 border-t border-[#30363d]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors disabled:opacity-50 flex items-center space-x-2 cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Creating...</span>
                </>
              ) : (
                <span>Create Project</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
