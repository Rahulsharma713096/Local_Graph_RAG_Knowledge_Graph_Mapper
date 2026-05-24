import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Activity, Cpu, HardDrive, Database, Wifi, Globe,
  TrendingUp, RefreshCw, Plus, Server, Zap, Loader2,
  Pencil, Trash2, WifiOff, FolderOpen, Upload, FileText,
  Folder, File, BarChart, LineChart as LineChartIcon,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  ResponsiveContainer, Area, AreaChart,
} from 'recharts';
import { useAppStore } from '../store/useAppStore';
import * as api from '../lib/api';
import type { DataSource, SystemMetrics, HealthStatus, DirEntry, HistoricalMetric } from '../types';

export function Dashboard() {
  const { metrics, setMetrics, healthStatus, setHealthStatus, dataSources, setDataSources, historicalMetrics, setHistoricalMetrics } = useAppStore();
  const [showAddSource, setShowAddSource] = useState(false);
  const [newSource, setNewSource] = useState({ name: '', source_type: 'csv', file_path: '', connection_string: '' });
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [addingSource, setAddingSource] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);
  const [editSource, setEditSource] = useState<DataSource | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  // File browser state
  const [showFileBrowser, setShowFileBrowser] = useState(false);
  const [browsePath, setBrowsePath] = useState('');
  const [browseEntries, setBrowseEntries] = useState<DirEntry[]>([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [browseError, setBrowseError] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [metricsData, health, sources, histMetrics] = await Promise.all([
        api.getDashboardMetrics(),
        api.getDashboardHealth(),
        api.listDataSources(),
        api.getHistoricalMetrics(2),
      ]);
      setMetrics(metricsData);
      setHealthStatus(health);
      setDataSources(sources);
      setHistoricalMetrics(histMetrics);
    } catch (e) {
      console.error('Failed to load dashboard data', e);
    } finally {
      setLoading(false);
    }
  };

  const addDataSource = async () => {
    setAddingSource(true);
    try {
      // If we have a file to upload, upload it first
      if (uploadFile) {
        await api.uploadDataSourceFile(uploadFile, newSource.name || undefined, newSource.source_type);
      } else {
        await api.createDataSource({
          name: newSource.name,
          source_type: newSource.source_type,
          file_path: newSource.file_path || undefined,
          connection_string: newSource.connection_string || undefined,
        });
      }
      setShowAddSource(false);
      setNewSource({ name: '', source_type: 'csv', file_path: '', connection_string: '' });
      setUploadFile(null);
      await loadData();
    } catch (e) {
      console.error('Failed to add data source', e);
    } finally {
      setAddingSource(false);
    }
  };

  const openFileBrowser = async (path = '') => {
    setBrowseLoading(true);
    setBrowseError(null);
    setBrowsePath(path);
    try {
      const result = await api.browseDirectory(path);
      setBrowseEntries(result.entries);
    } catch (e: any) {
      setBrowseError(e.message || 'Failed to browse directory');
      setBrowseEntries([]);
    } finally {
      setBrowseLoading(false);
    }
  };

  const handleFileSelect = (entry: DirEntry) => {
    if (entry.type === 'directory') {
      openFileBrowser(entry.path);
    } else {
      setNewSource({ ...newSource, file_path: entry.path, name: newSource.name || entry.name.replace(/\.\w+$/, '') });
      setShowFileBrowser(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadFile(file);
      setNewSource({
        ...newSource,
        name: newSource.name || file.name.replace(/\.\w+$/, ''),
        file_path: file.name,
      });
    }
  };

  const saveEditSource = async () => {
    if (!editSource) return;
    setSavingEdit(true);
    try {
      await api.updateDataSource(editSource.id, {
        name: editSource.name,
        source_type: editSource.source_type,
        connection_string: editSource.connection_string,
      });
      setEditSource(null);
      await loadData();
    } catch (e) {
      console.error('Failed to update data source', e);
    } finally {
      setSavingEdit(false);
    }
  };

  const seedData = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const result = await api.seedDemoData();
      setSeedResult(`Seeded: ${result.message}`);
      await loadData();
    } catch (e: any) {
      setSeedResult(`Error: ${e.message}`);
      console.error('Failed to seed data', e);
    } finally {
      setSeeding(false);
    }
  };

  const MetricCard = ({ title, value, unit, icon: Icon, color, sub }: {
    title: string; value: string | number; unit?: string; icon: any; color: string; sub?: string;
  }) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card-hover p-5"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{title}</p>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-2xl font-bold text-white">{value}</span>
            {unit && <span className="text-sm text-gray-400">{unit}</span>}
          </div>
          {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
        </div>
        <div className={`p-2.5 rounded-lg bg-${color}-500/10`}>
          <Icon className={`w-5 h-5 text-${color}-400`} />
        </div>
      </div>
      <div className="mt-4 h-1.5 bg-surface-700 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${typeof value === 'number' ? Math.min(value, 100) : 50}%` }}
          transition={{ duration: 1, ease: 'easeOut' }}
          className={`h-full rounded-full bg-${color}-500`}
        />
      </div>
    </motion.div>
  );

  const StatusBadge = ({ status }: { status: string }) => (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
      status === 'healthy' ? 'bg-emerald-500/10 text-emerald-400' :
      status === 'unhealthy' ? 'bg-red-500/10 text-red-400' :
      'bg-amber-500/10 text-amber-400'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${
        status === 'healthy' ? 'bg-emerald-500' :
        status === 'unhealthy' ? 'bg-red-500' :
        'bg-amber-500'
      }`} />
      {status}
    </span>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-primary-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">System Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Real-time monitoring and control center</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={seedData}
            disabled={seeding}
            className="btn-secondary text-xs disabled:opacity-50"
          >
            {seeding ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                Seeding...
              </>
            ) : (
              <>
                <Zap className="w-3.5 h-3.5 mr-1.5" />
                Seed Demo Data
              </>
            )}
          </button>
          <button onClick={loadData} className="btn-ghost p-2" disabled={loading}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Seed Result Notification */}
      {seedResult && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className={`glass-card p-3 flex items-center gap-2 ${
            seedResult.startsWith('Error') ? 'border-red-500/20' : 'border-emerald-500/20'
          }`}
        >
          <div className={`w-2 h-2 rounded-full ${seedResult.startsWith('Error') ? 'bg-red-500' : 'bg-emerald-500'}`} />
          <span className={`text-xs ${seedResult.startsWith('Error') ? 'text-red-400' : 'text-emerald-400'}`}>
            {seedResult}
          </span>
        </motion.div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="CPU Usage"
          value={metrics?.cpu_usage ?? 0}
          unit="%"
          icon={Cpu}
          color="primary"
          sub="Total system load"
        />
        <MetricCard
          title="RAM Usage"
          value={metrics?.ram_usage ?? 0}
          unit="%"
          icon={HardDrive}
          color="accent"
          sub={`${metrics?.ram_total ?? 0} GB total`}
        />
        <MetricCard
          title="GPU Usage"
          value={metrics?.gpu_usage ?? 'N/A'}
          unit={metrics?.gpu_usage ? '%' : ''}
          icon={Activity}
          color="blue"
          sub={metrics?.gpu_memory ? `${metrics.gpu_memory} GB used` : 'Not available'}
        />
        <MetricCard
          title="Active Pipelines"
          value={metrics?.active_pipelines ?? 0}
          icon={TrendingUp}
          color="amber"
          sub="Running processes"
        />
      </div>

      {/* SRS: Historical Metrics Chart — CPU/RAM over time using Recharts */}
      {historicalMetrics.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <BarChart className="w-4 h-4 text-primary-400" />
              System Metrics Over Time
            </h2>
            <div className="flex items-center gap-3 text-[10px]">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-primary-500" />
                <span className="text-gray-500">CPU</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className="text-gray-500">RAM</span>
              </div>
              {historicalMetrics.some(m => m.gpu_usage) && (
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                  <span className="text-gray-500">GPU</span>
                </div>
              )}
            </div>
          </div>
          <div style={{ height: '200px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={historicalMetrics.map(m => ({
                time: new Date(m.recorded_at).toLocaleTimeString(),
                cpu: m.cpu_usage,
                ram: m.ram_usage,
                gpu: m.gpu_usage || undefined,
              }))}>
                <defs>
                  <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="ramGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 10 }} stroke="#334155" />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} stroke="#334155" domain={[0, 100]} />
                <RechartsTooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Area type="monotone" dataKey="cpu" stroke="#6366f1" fill="url(#cpuGrad)" strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="ram" stroke="#10b981" fill="url(#ramGrad)" strokeWidth={2} dot={false} />
                {historicalMetrics.some(m => m.gpu_usage) && (
                  <Area type="monotone" dataKey="gpu" stroke="#f59e0b" fill="none" strokeWidth={2} strokeDasharray="4 4" dot={false} />
                )}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      )}

      {/* Health Status & Data Sources */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Health Status */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card p-5"
        >
          <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Wifi className="w-4 h-4 text-primary-400" />
            Service Health
          </h2>
          <div className="space-y-3">
            {healthStatus && Object.entries(healthStatus).map(([service, status]) => (
              <div key={service} className="flex items-center justify-between py-2 border-b border-surface-700/50 last:border-0">
                <span className="text-sm text-gray-400 capitalize">{service}</span>
                <StatusBadge status={status} />
              </div>
            ))}
          </div>
        </motion.div>

        {/* Data Sources */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Database className="w-4 h-4 text-primary-400" />
              Connected Data Sources
            </h2>
            <button
              onClick={() => setShowAddSource(true)}
              className="btn-primary text-xs py-1.5"
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              Add Source
            </button>
          </div>

          {dataSources.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Globe className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No data sources connected</p>
              <p className="text-xs mt-1">Click "Add Source" to connect your first data source</p>
            </div>
          ) : (
            <div className="space-y-2">
              {dataSources.map((ds) => (
                <div key={ds.id} className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 border border-surface-700/50">
                  <div>
                    <p className="text-sm font-medium text-gray-200">{ds.name}</p>
                    <p className="text-xs text-gray-500">{ds.source_type}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      ds.is_connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-500/10 text-gray-400'
                    }`}>
                      {ds.is_connected ? 'Connected' : 'Disconnected'}
                    </span>
                    {/* Edit button */}
                    <button
                      onClick={() => setEditSource(ds)}
                      className="p-1.5 rounded-lg text-xs text-blue-400 hover:bg-blue-500/10 transition-all"
                      title="Edit Data Source"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    {/* Issue #1: Disconnect button */}
                    {ds.is_connected && (
                      <button
                        onClick={async () => {
                          try {
                            await api.disconnectDataSource(ds.id);
                            await loadData();
                          } catch (e) {
                            console.error('Failed to disconnect', e);
                          }
                        }}
                        className="p-1.5 rounded-lg text-xs text-amber-400 hover:bg-amber-500/10 transition-all"
                        title="Disconnect"
                      >
                        <WifiOff className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {/* Delete button */}
                    <button
                      onClick={async () => {
                        if (!confirm(`Delete data source "${ds.name}"?`)) return;
                        try {
                          await api.deleteDataSource(ds.id);
                          await loadData();
                        } catch (e) {
                          console.error('Failed to delete', e);
                        }
                      }}
                      className="p-1.5 rounded-lg text-xs text-red-400 hover:bg-red-500/10 transition-all"
                      title="Delete Data Source"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>

      {/* Add Data Source Modal */}
      {showAddSource && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="glass-card p-6 w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto"
          >
            <h3 className="text-lg font-semibold text-white mb-4">Add Data Source</h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Name</label>
                <input
                  className="input-field"
                  value={newSource.name}
                  onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
                  placeholder="My CSV Data"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Type</label>
                <select
                  className="input-field"
                  value={newSource.source_type}
                  onChange={(e) => setNewSource({ ...newSource, source_type: e.target.value })}
                >
                  <option value="csv">CSV File</option>
                  <option value="sqlite">SQLite</option>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="mysql">MySQL</option>
                </select>
              </div>

              {/* File Upload Section */}
              <div>
                <label className="text-xs text-gray-400 mb-2 block">Upload File</label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-surface-600 rounded-lg p-4 text-center cursor-pointer hover:border-primary-500/50 hover:bg-primary-500/5 transition-all"
                >
                  {uploadFile ? (
                    <div className="flex items-center justify-center gap-2">
                      <FileText className="w-5 h-5 text-primary-400" />
                      <span className="text-sm text-gray-300">{uploadFile.name}</span>
                      <span className="text-xs text-gray-500">({(uploadFile.size / 1024).toFixed(1)} KB)</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); setUploadFile(null); }}
                        className="text-xs text-red-400 hover:text-red-300 ml-2"
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-1">
                      <Upload className="w-6 h-6 text-gray-500" />
                      <span className="text-sm text-gray-500">Click to upload a CSV file</span>
                      <span className="text-xs text-gray-600">or use the file browser below</span>
                    </div>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.tsv,.json,.txt"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                </div>
              </div>

              {/* File Browser Button */}
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Folder Path / File Path</label>
                <div className="flex gap-2">
                  <input
                    className="input-field flex-1"
                    value={newSource.file_path}
                    onChange={(e) => setNewSource({ ...newSource, file_path: e.target.value })}
                    placeholder="C:/path/to/data.csv"
                  />
                  <button
                    onClick={() => { setShowFileBrowser(true); openFileBrowser(''); }}
                    className="btn-secondary px-3"
                    title="Browse Files"
                  >
                    <FolderOpen className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Connection String (for DB sources) */}
              {newSource.source_type !== 'csv' && (
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Connection String</label>
                  <input
                    className="input-field"
                    value={newSource.connection_string}
                    onChange={(e) => setNewSource({ ...newSource, connection_string: e.target.value })}
                    placeholder="postgresql://user:pass@localhost:5432/db"
                  />
                </div>
              )}
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => { setShowAddSource(false); setUploadFile(null); }} className="btn-ghost" disabled={addingSource}>Cancel</button>
              <button onClick={addDataSource} className="btn-primary" disabled={addingSource || (!newSource.file_path && !uploadFile)}>
                {addingSource ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>Add Source</>
                )}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* File Browser Modal */}
      {showFileBrowser && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[60]">
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="glass-card p-6 w-full max-w-lg mx-4 max-h-[70vh] flex flex-col"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">File Browser</h3>
              <button
                onClick={() => setShowFileBrowser(false)}
                className="text-xs text-gray-500 hover:text-gray-300"
              >
                Close
              </button>
            </div>

            {/* Current path */}
            <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-surface-800 rounded-lg text-xs text-gray-400 font-mono truncate">
              <Folder className="w-3.5 h-3.5 text-primary-400 shrink-0" />
              <span className="truncate">{browsePath || '/'}</span>
            </div>

            {/* Entries */}
            <div className="flex-1 overflow-y-auto space-y-1 min-h-[200px]">
              {browseLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
                </div>
              ) : browseError ? (
                <div className="text-center py-8">
                  <p className="text-xs text-red-400">{browseError}</p>
                  <button onClick={() => openFileBrowser('')} className="mt-2 text-xs text-primary-400 hover:text-primary-300">
                    Browse from root
                  </button>
                </div>
              ) : browseEntries.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Folder className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-xs">Empty directory</p>
                </div>
              ) : (
                <>
                  {/* Parent directory */}
                  {browsePath && (
                    <button
                      onClick={() => openFileBrowser(browsePath.split('\\').slice(0, -1).join('\\') || browsePath.split('/').slice(0, -1).join('/') || '')}
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-surface-700/50 text-gray-400 text-xs transition-all"
                    >
                      <Folder className="w-4 h-4 text-amber-400" />
                      <span>.. (Parent Directory)</span>
                    </button>
                  )}
                  {browseEntries.map((entry, i) => (
                    <button
                      key={`${entry.path}-${i}`}
                      onClick={() => handleFileSelect(entry)}
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-surface-700/50 transition-all group"
                    >
                      {entry.type === 'directory' ? (
                        <Folder className="w-4 h-4 text-amber-400" />
                      ) : (
                        <FileText className="w-4 h-4 text-primary-400" />
                      )}
                      <div className="flex-1 min-w-0 text-left">
                        <p className="text-xs text-gray-300 truncate">{entry.name}</p>
                        {entry.size_display && (
                          <p className="text-[10px] text-gray-600">{entry.size_display}</p>
                        )}
                      </div>
                      <span className="text-[10px] text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity">
                        {entry.type === 'directory' ? 'Open' : 'Select'}
                      </span>
                    </button>
                  ))}
                </>
              )}
            </div>
          </motion.div>
        </div>
      )}

      {/* Edit Data Source Modal */}
      {editSource && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="glass-card p-6 w-full max-w-md mx-4"
          >
            <h3 className="text-lg font-semibold text-white mb-4">Edit Data Source</h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Name</label>
                <input
                  className="input-field"
                  value={editSource.name}
                  onChange={(e) => setEditSource({ ...editSource, name: e.target.value })}
                  placeholder="My Database"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Type</label>
                <select
                  className="input-field"
                  value={editSource.source_type}
                  onChange={(e) => setEditSource({ ...editSource, source_type: e.target.value })}
                >
                  <option value="csv">CSV File</option>
                  <option value="sqlite">SQLite</option>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="mysql">MySQL</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Connection String / File Path</label>
                <input
                  className="input-field"
                  value={editSource.connection_string || ''}
                  onChange={(e) => setEditSource({ ...editSource, connection_string: e.target.value })}
                  placeholder="data/sample.csv"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setEditSource(null)} className="btn-ghost" disabled={savingEdit}>Cancel</button>
              <button onClick={saveEditSource} className="btn-primary" disabled={savingEdit}>
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
    </div>
  );
}
