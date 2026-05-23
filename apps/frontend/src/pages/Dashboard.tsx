import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Activity, Cpu, HardDrive, Database, Wifi, Globe,
  TrendingUp, RefreshCw, Plus, Server, Zap,
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import * as api from '../lib/api';
import type { DataSource, SystemMetrics, HealthStatus } from '../types';

export function Dashboard() {
  const { metrics, setMetrics, healthStatus, setHealthStatus, dataSources, setDataSources } = useAppStore();
  const [showAddSource, setShowAddSource] = useState(false);
  const [newSource, setNewSource] = useState({ name: '', source_type: 'csv', connection_string: '' });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [metricsData, health, sources] = await Promise.all([
        api.getDashboardMetrics(),
        api.getDashboardHealth(),
        api.listDataSources(),
      ]);
      setMetrics(metricsData);
      setHealthStatus(health);
      setDataSources(sources);
    } catch (e) {
      console.error('Failed to load dashboard data', e);
    } finally {
      setLoading(false);
    }
  };

  const addDataSource = async () => {
    try {
      await api.createDataSource(newSource);
      setShowAddSource(false);
      setNewSource({ name: '', source_type: 'csv', connection_string: '' });
      loadData();
    } catch (e) {
      console.error('Failed to add data source', e);
    }
  };

  const seedData = async () => {
    try {
      await api.seedDemoData();
      loadData();
    } catch (e) {
      console.error('Failed to seed data', e);
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
        <RefreshCw className="w-6 h-6 text-primary-500 animate-spin" />
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
          <button onClick={seedData} className="btn-secondary text-xs">
            <Zap className="w-3.5 h-3.5 mr-1.5" />
            Seed Demo Data
          </button>
          <button onClick={loadData} className="btn-ghost p-2">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

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
            <button onClick={() => setShowAddSource(true)} className="btn-primary text-xs py-1.5">
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
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    ds.is_connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-500/10 text-gray-400'
                  }`}>
                    {ds.is_connected ? 'Connected' : 'Disconnected'}
                  </span>
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
            className="glass-card p-6 w-full max-w-md mx-4"
          >
            <h3 className="text-lg font-semibold text-white mb-4">Add Data Source</h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Name</label>
                <input
                  className="input-field"
                  value={newSource.name}
                  onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
                  placeholder="My Database"
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
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Connection String / File Path</label>
                <input
                  className="input-field"
                  value={newSource.connection_string}
                  onChange={(e) => setNewSource({ ...newSource, connection_string: e.target.value })}
                  placeholder="data/sample.csv"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowAddSource(false)} className="btn-ghost">Cancel</button>
              <button onClick={addDataSource} className="btn-primary">Add Source</button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
