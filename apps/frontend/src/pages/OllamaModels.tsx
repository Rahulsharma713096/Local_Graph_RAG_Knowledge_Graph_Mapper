import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Cpu, RefreshCw, Download, CheckCircle2, Star, Zap,
  Server, Gauge, Brain, Info,
} from 'lucide-react';
import * as api from '../lib/api';
import type { OllamaModel } from '../types';

export function OllamaModels() {
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [available, setAvailable] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [pulling, setPulling] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('');

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setLoading(true);
    try {
      const [status, modelData] = await Promise.all([
        api.getOllamaStatus(),
        api.listOllamaModels(),
      ]);
      setAvailable(status.available);
      setModels(modelData);
      const active = modelData.find((m) => m.is_active);
      if (active) setSelectedModel(active.name);
    } catch (e) {
      console.error('Failed to load Ollama models', e);
    } finally {
      setLoading(false);
    }
  };

  const handlePullModel = async (modelName: string) => {
    setPulling(modelName);
    try {
      await api.pullOllamaModel(modelName);
      loadModels();
    } catch (e) {
      console.error('Failed to pull model', e);
    } finally {
      setPulling(null);
    }
  };

  const handleSelectModel = async (modelName: string) => {
    try {
      await api.selectOllamaModel(modelName);
      setSelectedModel(modelName);
    } catch (e) {
      console.error('Failed to select model', e);
    }
  };

  const ModelCard = ({ model, index }: { model: OllamaModel; index: number }) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={`glass-card-hover p-5 relative overflow-hidden ${
        model.is_active ? 'ring-1 ring-primary-500/50' : ''
      }`}
    >
      {model.is_active && (
        <div className="absolute top-3 right-3">
          <span className="badge-primary text-[10px]">Active</span>
        </div>
      )}

      <div className="flex items-start gap-4">
        <div className={`p-2.5 rounded-lg ${
          model.is_active ? 'bg-primary-500/20' : 'bg-surface-700/50'
        }`}>
          <Cpu className={`w-5 h-5 ${model.is_active ? 'text-primary-400' : 'text-gray-500'}`} />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            {model.name}
            {model.is_active && <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />}
          </h3>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Server className="w-3 h-3" />
              <span>Size: <span className="text-gray-300">{model.model_size || 'Unknown'}</span></span>
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Gauge className="w-3 h-3" />
              <span>VRAM: <span className="text-gray-300">{model.vram_estimate || 'N/A'}</span></span>
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Brain className="w-3 h-3" />
              <span>Context: <span className="text-gray-300">{model.context_size || 'N/A'}</span></span>
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Zap className="w-3 h-3" />
              <span>Speed: <span className="text-gray-300">{model.speed_score || 'N/A'}/10</span></span>
            </div>
          </div>

          {/* RAG Suitability */}
          {model.rag_suitability && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-500">RAG Suitability</span>
                <span className="text-primary-400 font-medium">{model.rag_suitability}/10</span>
              </div>
              <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(model.rag_suitability / 10) * 100}%` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                  className="h-full rounded-full bg-gradient-to-r from-primary-500 to-accent-500"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-surface-700/50">
        {!model.is_active ? (
          <button
            onClick={() => handleSelectModel(model.name)}
            className="btn-primary text-xs py-1.5"
          >
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Select Model
          </button>
        ) : (
          <span className="text-xs text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            Active for queries
          </span>
        )}
        <button
          onClick={() => handlePullModel(model.name)}
          disabled={pulling === model.name}
          className="btn-ghost text-xs"
        >
          {pulling === model.name ? (
            <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <Download className="w-3 h-3 mr-1" />
          )}
          {pulling === model.name ? 'Pulling...' : 'Pull'}
        </button>
      </div>
    </motion.div>
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Ollama Models</h1>
          <p className="text-sm text-gray-500 mt-1">Manage local LLM models for RAG inference</p>
        </div>
        <button onClick={loadModels} className="btn-ghost">
          <RefreshCw className="w-4 h-4 mr-1.5" />
          Refresh
        </button>
      </div>

      {/* Status Banner */}
      <div className={`glass-card p-4 flex items-center gap-3 ${
        available ? 'border-emerald-500/20' : 'border-amber-500/20'
      }`}>
        <div className={`p-2 rounded-lg ${
          available ? 'bg-emerald-500/10' : 'bg-amber-500/10'
        }`}>
          {available
            ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            : <RefreshCw className="w-5 h-5 text-amber-400" />
          }
        </div>
        <div>
          <p className="text-sm font-medium text-white">
            Ollama {available ? 'Available' : 'Not Detected'}
          </p>
          <p className="text-xs text-gray-500">
            {available
              ? 'Local LLM service is running. You can select a model for RAG queries.'
              : 'Start Ollama on your system to enable local inference. Run: ollama serve'
            }
          </p>
        </div>
      </div>

      {/* Searchable Models Grid */}
      {models.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Cpu className="w-12 h-12 mx-auto text-gray-600 mb-3" />
          <p className="text-gray-400 font-medium">No models found</p>
          <p className="text-sm text-gray-600 mt-1">Pull a model to get started</p>
          <div className="flex justify-center gap-2 mt-4">
            {['llama3.1', 'mistral', 'phi3'].map((m) => (
              <button
                key={m}
                onClick={() => handlePullModel(m)}
                disabled={pulling === m}
                className="btn-secondary text-xs"
              >
                {pulling === m ? (
                  <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                ) : (
                  <Download className="w-3 h-3 mr-1" />
                )}
                Pull {m}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {models.map((model, index) => (
            <ModelCard key={model.name} model={model} index={index} />
          ))}
        </div>
      )}
    </div>
  );
}
