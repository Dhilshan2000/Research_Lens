import React from 'react';
import { X, Layers, Copy, Check } from 'lucide-react';

export default function ChunkInspectorModal({ isOpen, onClose, data }) {
  const [copiedIdx, setCopiedIdx] = React.useState(null);

  if (!isOpen || !data) return null;

  const handleCopy = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#30363d] bg-[#1a202c]">
          <div className="flex items-center space-x-2">
            <Layers className="w-5 h-5 text-indigo-400" />
            <div>
              <h3 className="text-base font-semibold text-white">Chunk & Metadata Inspector</h3>
              <p className="text-xs text-gray-400">
                {data.filename} • {data.total_chunks} tokenized chunk(s)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1 rounded-md transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Chunks List */}
        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          {data.chunks?.map((chunk, idx) => (
            <div
              key={chunk.chunk_id || idx}
              className="bg-[#0d1117] border border-[#30363d] rounded-lg p-4 space-y-2 text-xs"
            >
              <div className="flex items-center justify-between text-gray-400 pb-2 border-b border-[#30363d]/60">
                <div className="flex items-center space-x-2">
                  <span className="font-semibold text-white">Chunk #{idx + 1}</span>
                  <span className="font-mono text-[11px] text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                    {chunk.token_count || '~'} tokens
                  </span>
                </div>
                <div className="flex items-center space-x-3 text-[11px]">
                  {chunk.metadata?.page && <span>Page: {chunk.metadata.page}</span>}
                  {chunk.metadata?.section && <span>Section: {chunk.metadata.section}</span>}
                  {chunk.metadata?.sheet && <span>Sheet: {chunk.metadata.sheet}</span>}
                  <button
                    onClick={() => handleCopy(chunk.text, idx)}
                    className="p-1 hover:text-white transition-colors"
                    title="Copy chunk text"
                  >
                    {copiedIdx === idx ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <div className="text-gray-300 font-mono text-[11px] whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto pr-2">
                {chunk.text}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
