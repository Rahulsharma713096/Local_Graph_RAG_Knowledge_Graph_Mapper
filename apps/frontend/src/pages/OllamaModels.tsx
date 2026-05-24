import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cpu, RefreshCw, Download, CheckCircle2, Star, Zap,
  Server, Gauge, Brain, Info, CheckCircle, XCircle,
  MessageSquare, Send, Loader2, Terminal,
} from 'lucide-react';
import * as api from '../lib/api';
import { useAppStore } from '../store/useAppStore';
import type { OllamaModel } from '../types';

export function OllamaModels() {
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [available, setAvailable] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectingModel, setSelectingModel] = useState<string | null>(null);
  const [chatModel, setChatModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const storeSetSelectedModel = useAppStore((s) => s.setSelectedModel);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setLoading(true);
    setError(null);
    try {
      const [status, modelData] = await Promise.all([
        api.getOllamaStatus(),
        api.listOllamaModels(),
      ]);
      setAvailable(status.available);
      setModels(modelData);
      const active = modelData.find((m) => m.is_active);
      if (active) {
        setSelectedModel(active.name);
        // Sync backend's active model to global store on initial load
        storeSetSelectedModel(active.name);
      }
    } catch (e: any) {
      console.error('Failed to load Ollama models', e);
      setError(e.message || 'Failed to load models');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectModel = async (modelName: string) => {
    // Close any open chat panel when switching models
    setChatModel(null);
    setSelectingModel(modelName);
    setError(null);
    try {
      const result = await api.selectOllamaModel(modelName);
      setSelectedModel(modelName);
      // Sync to global store so QueryConsole and other tabs pick it up
      storeSetSelectedModel(modelName);
      // Update local state to reflect active model
      setModels((prev) =>
        prev.map((m) => ({
          ...m,
          is_active: m.name === modelName,
        }))
      );
    } catch (e: any) {
      console.error('Failed to select model', e);
      setError(e.message || 'Failed to select model');
    } finally {
      setSelectingModel(null);
    }
  };

  const ChatPanel = ({ modelName, onClose }: { modelName: string; onClose: () => void }) => {
    const [chatInput, setChatInput] = useState('');
    const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([]);
    const [chatLoading, setChatLoading] = useState(false);
    const [chatError, setChatError] = useState<string | null>(null);
    const chatEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatMessages, chatLoading]);

    const handleChatSubmit = async () => {
      const msg = chatInput.trim();
      if (!msg || chatLoading) return;
      setChatInput('');
      setChatError(null);
      setChatMessages((prev) => [...prev, { role: 'user', content: msg }]);
      setChatLoading(true);
      try {
        const result = await api.chatWithOllamaModel(msg, modelName);
        setChatMessages((prev) => [...prev, { role: 'assistant', content: result.response }]);
      } catch (e: any) {
        setChatError(e.message || 'Chat failed');
      } finally {
        setChatLoading(false);
      }
    };

    return (
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: 'auto' }}
        exit={{ opacity: 0, height: 0 }}
        className="glass-card overflow-hidden border-primary-500/20"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700/50">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-primary-400" />
            <span className="text-sm font-semibold text-white">Chat — {modelName}</span>
          </div>
          <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-surface-700/50">
            Close
          </button>
        </div>
        <div className="p-4 h-64 overflow-y-auto space-y-3 font-mono text-xs">
          {chatMessages.length === 0 && !chatLoading && (
            <div className="text-center text-gray-500 py-8">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>Type a message below to test {modelName}</p>
            </div>
          )}
          {chatMessages.map((msg, i) => (
            <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              <div className={`max-w-[85%] p-3 rounded-lg ${
                msg.role === 'user'
                  ? 'bg-primary-500/15 text-primary-300 border border-primary-500/20'
                  : 'bg-surface-800/80 text-gray-300 border border-surface-700/50'
              }`}>
                <div className="text-[10px] mb-1 opacity-60">
                  {msg.role === 'user' ? 'You' : modelName}
                </div>
                <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="flex gap-2">
              <div className="p-3 rounded-lg bg-surface-800/80 border border-surface-700/50">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-3 h-3 text-primary-400 animate-spin" />
                  <span className="text-gray-500">{modelName} is generating...</span>
                </div>
              </div>
            </div>
          )}
          {chatError && (
            <div className="p-2 rounded-lg bg-red-500/10 text-red-400 text-center border border-red-500/20">
              {chatError}
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
        <div className="p-3 border-t border-surface-700/50 flex gap-2">
          <input
            className="input-field flex-1 text-sm"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleChatSubmit()}
            placeholder={`Message ${modelName}...`}
            disabled={chatLoading}
          />
          <button
            onClick={handleChatSubmit}
            disabled={chatLoading || !chatInput.trim()}
            className="btn-primary disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </motion.div>
    );
  };

  const ModelCard = ({ model, index }: { model: OllamaModel; index: number }) => {
    const isThisSelected = model.is_active || model.name === selectedModel;
    const isSelecting = selectingModel === model.name;

    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.05 }}
        className={`glass-card-hover p-5 relative overflow-hidden transition-all duration-300 ${
          isThisSelected
            ? 'ring-2 ring-emerald-500/50 bg-emerald-500/5'
            : 'ring-1 ring-transparent hover:ring-primary-500/30'
        }`}
      >
        {isThisSelected && (
          <div className="absolute top-3 right-3">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              <CheckCircle className="w-3 h-3" />
              Active
            </span>
          </div>
        )}

        <div className="flex items-start gap-4">
          <div className={`p-2.5 rounded-lg transition-all duration-300 ${
            isThisSelected ? 'bg-emerald-500/20 ring-1 ring-emerald-500/30' : 'bg-surface-700/50'
          }`}>
            <Cpu className={`w-5 h-5 ${isThisSelected ? 'text-emerald-400' : 'text-gray-500'}`} />
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              {model.name}
              {isThisSelected && <Star className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />}
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

        {/* Select Model Button - Only shows if not active */}
        <div className="mt-4 pt-3 border-t border-surface-700/50">
          {isThisSelected ? (
            <div className="flex items-center gap-2">
              <div className="flex-1 flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 rounded-lg px-3 py-2">
                <CheckCircle2 className="w-4 h-4" />
                <span className="font-medium">Active for RAG queries</span>
              </div>
              {/* Issue #9: Chat button to test selected model */}
              <button
                onClick={() => setChatModel(model.name)}
                className="px-3 py-2 rounded-lg text-xs font-medium bg-primary-500/10 text-primary-400 border border-primary-500/20 hover:bg-primary-500/20 transition-all flex items-center gap-1.5"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                Chat
              </button>
            </div>
          ) : (
            <button
              onClick={() => handleSelectModel(model.name)}
              disabled={isSelecting}
              className="w-full btn-primary text-xs py-2 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isSelecting ? (
                <>
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  Selecting...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Use This Model
                </>
              )}
            </button>
          )}
        </div>
      </motion.div>
    );
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
          <h1 className="text-2xl font-bold text-white">Ollama Models</h1>
          <p className="text-sm text-gray-500 mt-1">Manage local LLM models for RAG inference</p>
        </div>
        <button onClick={loadModels} className="btn-ghost">
          <RefreshCw className="w-4 h-4 mr-1.5" />
          Refresh
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 border-red-500/20 flex items-center gap-3"
        >
          <div className="p-2 rounded-lg bg-red-500/10">
            <XCircle className="w-5 h-5 text-red-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-red-400">Error</p>
            <p className="text-xs text-gray-500">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-xs text-gray-500 hover:text-gray-300">
            Dismiss
          </button>
        </motion.div>
      )}

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
              ? 'Local LLM service is running. Select a model below for RAG queries.'
              : 'Start Ollama on your system to enable local inference. Run: ollama serve'
            }
          </p>
        </div>
      </div>

      {/* Models Grid - Only shows models already present in system (Issue #5 fix) */}
      {models.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Cpu className="w-12 h-12 mx-auto text-gray-600 mb-3" />
          <p className="text-gray-400 font-medium">No models found</p>
          <p className="text-sm text-gray-600 mt-1">
            Pull models via Ollama CLI first (e.g., `ollama pull llama3.1`), then refresh.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {models.map((model, index) => (
              <ModelCard key={model.name} model={model} index={index} />
            ))}
          </div>

          {/* Issue #9: Chat panel for testing selected model */}
          <AnimatePresence>
            {chatModel && (
              <ChatPanel
                modelName={chatModel}
                onClose={() => setChatModel(null)}
              />
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  );
}
