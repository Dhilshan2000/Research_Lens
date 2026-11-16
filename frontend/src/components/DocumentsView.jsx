import React, { useState } from 'react';
import {
  UploadCloud,
  FileText,
  FileSpreadsheet,
  FileCode,
  Trash2,
  Layers,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { uploadDocuments, deleteDocument, inspectChunks } from '../api';
import ChunkInspectorModal from './ChunkInspectorModal';

export default function DocumentsView({ project, documents = [], onRefreshProject }) {
  const [isUploading, setIsUploading] = useState(false);
  const [inspectorData, setInspectorData] = useState(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [inspectLoading, setInspectLoading] = useState(false);

  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    setIsUploading(true);
    try {
      await uploadDocuments(project.id, files);
      onRefreshProject();
      e.target.value = '';
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (docId, filename) => {
    if (!confirm(`Delete document "${filename}"?`)) return;
    try {
      await deleteDocument(docId);
      onRefreshProject();
    } catch (err) {
      alert(`Failed to delete document: ${err.message}`);
    }
  };

  const handleInspect = async (docId) => {
    setInspectLoading(true);
    try {
      const data = await inspectChunks(docId);
      setInspectorData(data);
      setIsInspectorOpen(true);
    } catch (err) {
      alert(`Failed to load chunks: ${err.message}`);
    } finally {
      setInspectLoading(false);
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  const getFormatIcon = (type) => {
    switch (type.toLowerCase()) {
      case 'pdf':
        return <FileText className="w-4 h-4 text-rose-400" />;
      case 'docx':
      case 'doc':
        return <FileText className="w-4 h-4 text-blue-400" />;
      case 'csv':
      case 'xlsx':
      case 'xls':
        return <FileSpreadsheet className="w-4 h-4 text-emerald-400" />;
      default:
        return <FileCode className="w-4 h-4 text-gray-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Drop Area */}
      <div className="bg-[#161b22] border-2 border-dashed border-[#30363d] hover:border-indigo-500/60 rounded-xl p-8 text-center transition-colors">
        <UploadCloud className="w-10 h-10 text-indigo-400 mx-auto mb-3" />
        <h4 className="text-sm font-semibold text-white mb-1">
          Upload Research Papers & Supplementary Data
        </h4>
        <p className="text-xs text-gray-400 mb-4 max-w-md mx-auto">
          Supports multi-format parsing for <strong>PDF</strong>, <strong>DOCX</strong>, <strong>TXT</strong>, and tabular datasets (<strong>CSV</strong>, <strong>XLSX</strong>).
        </p>

        <label className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-4 py-2 rounded-lg cursor-pointer transition-colors shadow-sm">
          <span>{isUploading ? 'Ingesting and Parsing...' : 'Select Files to Ingest'}</span>
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt,.csv,.xlsx,.xls"
            onChange={handleFileChange}
            disabled={isUploading}
            className="hidden"
          />
        </label>
      </div>

      {/* Documents Table */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-[#30363d] flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Ingested Document Library</h3>
            <p className="text-xs text-gray-400">
              {documents.length} document(s) registered in this project
            </p>
          </div>
        </div>

        {documents.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No research documents uploaded yet. Upload PDFs or data files above.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#30363d] text-gray-400 bg-[#0d1117]">
                  <th className="py-3 px-4 font-semibold">Document Name</th>
                  <th className="py-3 px-4 font-semibold">Format</th>
                  <th className="py-3 px-4 font-semibold">File Size</th>
                  <th className="py-3 px-4 font-semibold">Parsed Chunks</th>
                  <th className="py-3 px-4 font-semibold">Uploaded</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#30363d]/60">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 px-4 font-medium text-white flex items-center space-x-2.5">
                      {getFormatIcon(doc.file_type)}
                      <span className="truncate max-w-xs">{doc.filename}</span>
                    </td>
                    <td className="py-3 px-4 uppercase font-mono text-gray-400">
                      {doc.file_type}
                    </td>
                    <td className="py-3 px-4 text-gray-400 font-mono">
                      {formatSize(doc.file_size)}
                    </td>
                    <td className="py-3 px-4 text-indigo-400 font-mono font-medium">
                      {doc.parsed_chunks_count} chunks
                    </td>
                    <td className="py-3 px-4 text-gray-500">
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <button
                        onClick={() => handleInspect(doc.id)}
                        disabled={inspectLoading}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-[#0d1117] hover:bg-gray-800 border border-[#30363d] text-gray-300 hover:text-white transition-colors cursor-pointer"
                        title="Inspect Chunks & Token Metadata"
                      >
                        <Layers className="w-3.5 h-3.5" />
                        <span>Inspect</span>
                      </button>
                      <button
                        onClick={() => handleDelete(doc.id, doc.filename)}
                        className="p-1 rounded hover:bg-rose-500/20 text-gray-400 hover:text-rose-400 transition-colors cursor-pointer"
                        title="Delete Document"
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

      {/* Chunk Inspector Modal */}
      <ChunkInspectorModal
        isOpen={isInspectorOpen}
        onClose={() => setIsInspectorOpen(false)}
        data={inspectorData}
      />
    </div>
  );
}
