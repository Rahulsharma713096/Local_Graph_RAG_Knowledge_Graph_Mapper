import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  GitBranch, Play, Square, CheckCircle2, XCircle, Clock,
  AlertCircle, RefreshCw, Plus, ListChecks,
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import * as api from '../lib/api';
import type { Pipeline } from '../types';

const stageColors: Record<string, string> = {
  Extraction: 'blue',
  Cleaning: 'purple',
  NER: 'amber',
  'Graph Build': 'emerald',
  Embeddings: 'rose',
  'FAISS Indexing': 'cyan',
  'Community Detection': 'indigo',
};

const stageIcons: Record<string, string> = {
  Extraction: '📥',
  Cleaning: '🧹',
  NER: '🔍',
  'Graph Build': '🕸️',
  Embeddings: '🧠',
  'FAISS Indexing': '📊',
  'Community Detection': '👥',
};

export function Pipeline() {
  const { pipelines, setPipelines } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newPipeline, setNewPipeline] = useState({ name: '', data_source_id: 0 });
  const [runningIds, setRunningIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    loadPipelines();
    const interval = setInterval(loadPipelines, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadPipelines = async () => {
    try {
      const data = await api.listPipelines();
      setPipelines(data);
    } catch (e) {
      console.error('Failed to load pipelines', e);
    } finally {
      setLoading(false);
    }
  };

  const createPipeline = async () => {
    try {
      await api.createPipeline({ ...newPipeline, data_source_id: newPipeline.data_source_id || 1 });
      setShowCreate(false);
      setNewPipeline({ name: '', data_source_id: 0 });
      loadPipelines();
    } catch (e) {
      console.error('Failed to create pipeline', e);
    }
  };

  const startPipeline = async (id: number) => {
    setRunningIds((prev) => new Set(prev).add(id));
    try {
      await api.runPipeline(id);
    } catch (e) {
      console.error('Failed to start pipeline', e);
    }
  };

  const StatusIcon = ({ status }: { status: string }) => {
    switch (status) {
      case 'completed': return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'running': return <RefreshCw className="w-4 h-4 text-primary-400 animate-spin" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-400" />;
      default: return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-primary-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Pipeline Jobs</h1>
          <p className="text-sm text-gray-500 mt-1">Monitor and manage ETL + Knowledge Graph pipelines</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary text-sm">
          <Plus className="w-4 h-4 mr-1.5" />
          New Pipeline
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total', value: pipelines.length, color: 'text-white' },
          { label: 'Running', value: pipelines.filter((p) => p.status === 'running').length, color: 'text-primary-400' },
          { label: 'Completed', value: pipelines.filter((p) => p.status === 'completed').length, color: 'text-emerald-400' },
          { label: 'Failed', value: pipelines.filter((p) => p.status === 'failed').length, color: 'text-red-400' },
        ].map((stat) => (
          <div key={stat.label} className="glass-card p-4 text-center">
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-xs text-gray-500 mt-1">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Pipeline List */}
      {pipelines.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <GitBranch className="w-12 h-12 mx-auto text-gray-600 mb-3" />
          <p className="text-gray-400 font-medium">No pipelines yet</p>
          <p className="text-sm text-gray-600 mt-1">Create a pipeline to start processing data</p>
        </div>
      ) : (
        <div className="space-y-4">
          {pipelines.map((pipeline, index) => (
            <motion.div
              key={pipeline.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className="glass-card-hover p-5"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <StatusIcon status={pipeline.status} />
                  <div>
                    <h3 className="text-sm font-semibold text-white">{pipeline.name}</h3>
                    <p className="text-xs text-gray-500">
                      {pipeline.current_stage ? `Stage: ${pipeline.current_stage}` : 'Waiting...'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`badge-${
                    pipeline.status === 'completed' ? 'success' :
                    pipeline.status === 'running' ? 'info' :
                    pipeline.status === 'failed' ? 'error' : 'warning'
                  } text-xs`}>
                    {pipeline.status}
                  </span>
                  {pipeline.status === 'pending' && (
                    <button
                      onClick={() => startPipeline(pipeline.id)}
                      className="btn-primary text-xs py-1.5"
                    >
                      <Play className="w-3 h-3 mr-1" />
                      Run
                    </button>
                  )}
                </div>
              </div>

              {/* Progress Bar */}
              <div className="h-2 bg-surface-700 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${pipeline.progress}%` }}
                  transition={{ duration: 0.5 }}
                  className={`h-full rounded-full ${
                    pipeline.status === 'completed' ? 'bg-emerald-500' :
                    pipeline.status === 'failed' ? 'bg-red-500' :
                    'bg-gradient-to-r from-primary-500 to-accent-500'
                  }`}
                />
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-xs text-gray-500">{pipeline.progress.toFixed(0)}%</span>
                {pipeline.error_message && (
                  <span className="text-xs text-red-400 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    {pipeline.error_message}
                  </span>
                )}
              </div>

              {/* Pipeline Stages */}
              {pipeline.stages && (
                <div className="mt-4 grid grid-cols-7 gap-2">
                  {Object.entries(pipeline.stages).map(([stageKey, stageVal]: [string, any]) => (
                    <div
                      key={stageKey}
                      className={`text-center p-2 rounded-lg text-xs ${
                        stageVal?.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' :
                        stageVal?.status === 'running' ? 'bg-primary-500/10 text-primary-400' :
                        'bg-surface-800/50 text-gray-600'
                      }`}
                    >
                      <div className="mb-1">{stageIcons[stageKey.charAt(0).toUpperCase() + stageKey.slice(1)] || '📋'}</div>
                      <div className="capitalize">{stageKey.replace(/_/g, ' ')}</div>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}

      {/* Create Pipeline Modal */}
      <AnimatePresence>
        {showCreate && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-md mx-4"
            >
              <h3 className="text-lg font-semibold text-white mb-4">New Pipeline</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Pipeline Name</label>
                  <input
                    className="input-field"
                    value={newPipeline.name}
                    onChange={(e) => setNewPipeline({ ...newPipeline, name: e.target.value })}
                    placeholder="My ETL Pipeline"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Data Source ID</label>
                  <input
                    type="number"
                    className="input-field"
                    value={newPipeline.data_source_id || ''}
                    onChange={(e) => setNewPipeline({ ...newPipeline, data_source_id: parseInt(e.target.value) || 0 })}
                    placeholder="1"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 mt-6">
                <button onClick={() => setShowCreate(false)} className="btn-ghost">Cancel</button>
                <button onClick={createPipeline} className="btn-primary">Create</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
