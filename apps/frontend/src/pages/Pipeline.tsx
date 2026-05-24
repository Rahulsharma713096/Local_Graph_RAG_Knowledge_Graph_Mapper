import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  GitBranch, Play, Square, CheckCircle2, XCircle, Clock,
  AlertCircle, RefreshCw, Plus, ListChecks, Loader2,
  Pencil, Trash2,
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import * as api from '../lib/api';
import type { Pipeline, DataSource } from '../types';

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
  extraction: '📥',
  cleaning: '🧹',
  ner: '🔍',
  graph_build: '🕸️',
  embeddings: '🧠',
  faiss_indexing: '📊',
  community_detection: '👥',
};

export function Pipeline() {
  const { pipelines, setPipelines } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newPipeline, setNewPipeline] = useState({ name: '', data_source_name: '' });
  const [runningIds, setRunningIds] = useState<Set<number>>(new Set());
  const [editPipeline, setEditPipeline] = useState<Pipeline | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loadingDs, setLoadingDs] = useState(false);

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

  const loadDataSources = async () => {
    setLoadingDs(true);
    try {
      const sources = await api.listDataSources();
      setDataSources(sources);
    } catch (e) {
      console.error('Failed to load data sources', e);
    } finally {
      setLoadingDs(false);
    }
  };

  const createPipeline = async () => {
    // Find the data source ID that matches the selected name
    const selectedDs = dataSources.find(ds => ds.name === newPipeline.data_source_name);
    if (!selectedDs) {
      console.error('No data source selected');
      return;
    }
    try {
      const created = await api.createPipeline({ data_source_id: selectedDs.id, name: newPipeline.name });
      setShowCreate(false);
      setNewPipeline({ name: '', data_source_name: '' });
      // Issue #3: Auto-start pipeline after creation so it shows as "running" immediately
      await api.runPipeline(created.id);
      // Refresh immediately — the backend already set status to "running"
      loadPipelines();
    } catch (e) {
      console.error('Failed to create pipeline', e);
    }
  };

  const saveEditPipeline = async () => {
    if (!editPipeline) return;
    setSavingEdit(true);
    try {
      await api.updatePipeline(editPipeline.id, {
        name: editPipeline.name,
      });
      setEditPipeline(null);
      loadPipelines();
    } catch (e) {
      console.error('Failed to update pipeline', e);
    } finally {
      setSavingEdit(false);
    }
  };

  const startPipeline = async (id: number) => {
    setRunningIds((prev) => new Set(prev).add(id));
    try {
      await api.runPipeline(id);
      // Poll for updates after starting
      setTimeout(loadPipelines, 2000);
    } catch (e) {
      console.error('Failed to start pipeline', e);
    } finally {
      setRunningIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const StatusIcon = ({ status }: { status: string }) => {
    switch (status) {
      case 'completed': return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'running': return <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-400" />;
      default: return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStageDisplayName = (key: string): string => {
    const nameMap: Record<string, string> = {
      extraction: 'Extraction',
      cleaning: 'Cleaning',
      ner: 'NER',
      graph_build: 'Graph Build',
      embeddings: 'Embeddings',
      faiss_indexing: 'FAISS Indexing',
      community_detection: 'Community Detection',
    };
    return nameMap[key] || key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-primary-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Pipeline Jobs</h1>
          <p className="text-sm text-gray-500 mt-1">Monitor and manage ETL + Knowledge Graph pipelines</p>
        </div>          <button onClick={() => { setShowCreate(true); loadDataSources(); }} className="btn-primary text-sm">
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
                      {pipeline.current_stage ? `Stage: ${pipeline.current_stage}` : 
                       pipeline.status === 'completed' ? 'All stages complete' :
                       pipeline.status === 'failed' ? 'Pipeline failed' :
                       'Waiting to start...'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                    pipeline.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' :
                    pipeline.status === 'running' ? 'bg-primary-500/10 text-primary-400' :
                    pipeline.status === 'failed' ? 'bg-red-500/10 text-red-400' :
                    'bg-amber-500/10 text-amber-400'
                  }`}>
                    {pipeline.status === 'running' && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
                    {pipeline.status}
                  </span>
                  {(pipeline.status === 'pending' || pipeline.status === 'failed') && (
                    <button
                      onClick={() => startPipeline(pipeline.id)}
                      disabled={runningIds.has(pipeline.id)}
                      className="btn-primary text-xs py-1.5 disabled:opacity-50"
                    >
                      {runningIds.has(pipeline.id) ? (
                        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                      ) : (
                        <Play className="w-3 h-3 mr-1" />
                      )}
                      {pipeline.status === 'failed' ? 'Retry' : 'Run'}
                    </button>
                  )}
                  {/* Edit pipeline button */}
                  <button
                    onClick={() => setEditPipeline(pipeline)}
                    className="p-1.5 rounded-lg text-xs text-blue-400 hover:bg-blue-500/10 transition-all"
                    title="Edit Pipeline"
                    disabled={pipeline.status === 'running'}
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  {/* Issue #2: Delete pipeline button */}
                  <button
                    onClick={async () => {
                      if (!confirm('Delete this pipeline?')) return;
                      try {
                        await api.deletePipeline(pipeline.id);
                        loadPipelines();
                      } catch (e) {
                        console.error('Failed to delete pipeline', e);
                      }
                    }}
                    className="p-1.5 rounded-lg text-xs text-red-400 hover:bg-red-500/10 transition-all"
                    title="Delete Pipeline"
                    disabled={pipeline.status === 'running'}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
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
                  {Object.entries(pipeline.stages).map(([stageKey, stageVal]: [string, any]) => {
                    // Handle both string arrays and object-based stages
                    const stageStatus = typeof stageVal === 'string' ? null : stageVal?.status;
                    const stageName = getStageDisplayName(stageKey);
                    return (
                      <div
                        key={stageKey}
                        className={`text-center p-2 rounded-lg text-xs transition-all ${
                          stageStatus === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                          stageStatus === 'running' ? 'bg-primary-500/10 text-primary-400 border border-primary-500/20 animate-pulse' :
                          stageStatus === 'failed' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                          pipeline.status === 'completed' ? 'bg-emerald-500/5 text-emerald-400/60' :
                          'bg-surface-800/50 text-gray-600 border border-surface-700/30'
                        }`}
                      >
                        <div className="mb-1">{stageIcons[stageKey] || '📋'}</div>
                        <div className="capitalize">{stageName}</div>
                        {stageStatus && (
                          <div className="mt-1">
                            {stageStatus === 'completed' ? '✓' : 
                             stageStatus === 'running' ? '⟳' : 
                             stageStatus === 'failed' ? '✗' : ''}
                          </div>
                        )}
                      </div>
                    );
                  })}
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
                  <label className="text-xs text-gray-400 mb-1 block">Data Source</label>
                  <select
                    className="input-field"
                    value={newPipeline.data_source_name}
                    onChange={(e) => setNewPipeline({ ...newPipeline, data_source_name: e.target.value })}
                  >
                    <option value="">Select a data source...</option>
                    {loadingDs ? (
                      <option disabled>Loading...</option>
                    ) : (
                      dataSources.map((ds) => (
                        <option key={ds.id} value={ds.name}>
                          {ds.name}
                        </option>
                      ))
                    )}
                    {!loadingDs && dataSources.length === 0 && (
                      <option disabled>No data sources available</option>
                    )}
                  </select>
                  {!loadingDs && dataSources.length === 0 && (
                    <p className="text-xs text-amber-400 mt-1">No data sources found. Upload one from the Dashboard first.</p>
                  )}
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

      {/* Edit Pipeline Modal */}
      <AnimatePresence>
        {editPipeline && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-md mx-4"
            >
              <h3 className="text-lg font-semibold text-white mb-4">Edit Pipeline</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Pipeline Name</label>
                  <input
                    className="input-field"
                    value={editPipeline.name}
                    onChange={(e) => setEditPipeline({ ...editPipeline, name: e.target.value })}
                    placeholder="My ETL Pipeline"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 mt-6">
                <button onClick={() => setEditPipeline(null)} className="btn-ghost" disabled={savingEdit}>Cancel</button>
                <button onClick={saveEditPipeline} className="btn-primary" disabled={savingEdit}>
                  {savingEdit ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Changes'
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
