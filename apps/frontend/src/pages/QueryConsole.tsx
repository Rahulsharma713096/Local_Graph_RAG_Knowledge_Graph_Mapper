import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send, Terminal, Code2, ListChecks, Clock,
  ChevronRight, Search, Layers, Loader2, Sparkles,
} from 'lucide-react';
import * as api from '../lib/api';
import { useAppStore } from '../store/useAppStore';
import type { QueryResult, QueryHistoryItem } from '../types';

const stepIcons: Record<string, string> = {
  'Embed Query': '🧠',
  'Retrieve Graph Context': '🔍',
  'Generate Cypher': '📝',
  'Execute Graph Search': '🕸️',
  'Generate Answer': '✨',
};

export function QueryConsole() {
  const [query, setQuery] = useState('');
  const [traversalDepth, setTraversalDepth] = useState(2);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showCypher, setShowCypher] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);
  const { selectedModel } = useAppStore();

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [result]);

  const loadHistory = async () => {
    try {
      const data = await api.getQueryHistory(10);
      setHistory(data);
    } catch (e) {
      console.error('Failed to load history', e);
    }
  };

  const handleSubmit = async () => {
    if (!query.trim() || loading) return;

    setLoading(true);
    setResult(null);

    try {
      const data = await api.queryGraph({
        query: query.trim(),
        traversal_depth: traversalDepth,
        model: selectedModel || undefined,
      });
      setResult(data);
      loadHistory();
    } catch (e: any) {
      setResult({
        answer: `Error: ${e.message}`,
        execution_time_ms: 0,
        pipeline_steps: [],
      });
    } finally {
      setLoading(false);
    }
  };

  const loadFromHistory = (item: QueryHistoryItem) => {
    setQuery(item.natural_query);
    setShowHistory(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Query Console</h1>
          <p className="text-sm text-gray-500 mt-1">Natural language querying with graph-aware RAG</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Query Input + Results */}
        <div className="lg:col-span-2 space-y-4">
          {/* Query Input */}
          <div className="glass-card p-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-gray-500" />
                <span className="text-xs text-gray-500">Traversal Depth:</span>
              </div>
              {[1, 2, 3, 5].map((d) => (
                <button
                  key={d}
                  onClick={() => setTraversalDepth(d)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                    traversalDepth === d
                      ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                      : 'bg-surface-700/50 text-gray-400 border border-surface-700 hover:border-surface-600'
                  }`}
                >
                  {d}
                </button>
              ))}
              <div className="flex-1" />
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="btn-ghost text-xs"
              >
                <Clock className="w-3 h-3 mr-1" />
                History
              </button>
            </div>

            <div className="flex gap-3">
              <input
                className="input-field flex-1"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                placeholder="Ask anything about your knowledge graph..."
              />
              <button
                onClick={handleSubmit}
                disabled={loading || !query.trim()}
                className="btn-primary disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* Pipeline Visualization */}
          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-2 mb-3">
                <Loader2 className="w-4 h-4 text-primary-500 animate-spin" />
                <span className="text-sm text-gray-400">Processing query...</span>
              </div>
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {['Embed Query', 'Retrieve Context', 'Generate Cypher', 'Execute Search', 'Generate Answer'].map((step, i) => (
                  <div key={step} className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-500/10 border border-primary-500/20 animate-pulse">
                      <span className="text-xs">{stepIcons[step]}</span>
                      <span className="text-xs text-primary-400">{step}</span>
                    </div>
                    {i < 4 && <ChevronRight className="w-3 h-3 text-gray-600" />}
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Result */}
          <AnimatePresence>
            {result && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                {/* Answer */}
                <div className="glass-card p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-primary-400" />
                      Answer
                    </h3>
                    <span className="text-xs text-gray-500">
                      {(result.execution_time_ms / 1000).toFixed(2)}s
                    </span>
                  </div>
                  <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {result.answer}
                  </div>
                </div>

                {/* Pipeline Steps */}
                {result.pipeline_steps.length > 0 && (
                  <div className="glass-card p-4">
                    <h3 className="text-xs font-semibold text-white mb-3 flex items-center gap-2">
                      <ListChecks className="w-3.5 h-3.5 text-primary-400" />
                      Pipeline Steps
                    </h3>
                    <div className="space-y-2">
                      {result.pipeline_steps.map((step, i) => (
                        <div key={i} className="flex items-center gap-3 py-1">
                          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                            step.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                            step.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                            'bg-primary-500/20 text-primary-400'
                          }`}>
                            {step.status === 'completed' ? '✓' : step.status === 'failed' ? '✗' : '○'}
                          </div>
                          <span className="text-xs text-gray-400">{step.step}</span>
                          {step.error && <span className="text-xs text-red-400 ml-auto">{step.error}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Generated Cypher */}
                {result.generated_cypher && (
                  <div className="glass-card p-4">
                    <button
                      onClick={() => setShowCypher(!showCypher)}
                      className="flex items-center gap-2 text-xs font-semibold text-white mb-2"
                    >
                      <Code2 className="w-3.5 h-3.5 text-primary-400" />
                      Generated Cypher
                      <ChevronRight className={`w-3 h-3 transition-transform ${showCypher ? 'rotate-90' : ''}`} />
                    </button>
                    {showCypher && (
                      <pre className="p-3 bg-surface-900 rounded-lg text-xs text-accent-400 font-mono overflow-auto">
                        {result.generated_cypher}
                      </pre>
                    )}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right: Terminal + History */}
        <div className="space-y-4">
          {/* Terminal-style logs */}
          <div className="glass-card">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-surface-700/50">
              <Terminal className="w-4 h-4 text-primary-400" />
              <span className="text-xs font-semibold text-white">Terminal</span>
            </div>
            <div
              ref={terminalRef}
              className="p-4 h-64 overflow-auto font-mono text-xs space-y-1"
            >
              <div className="text-emerald-400">$ graphrag query ready</div>
              <div className="text-gray-500">└─ Ollama: {selectedModel || 'default'}</div>
              <div className="text-gray-500">└─ Traversal depth: {traversalDepth}</div>
              {loading && (
                <div className="text-primary-400 animate-pulse">└─ Processing query...</div>
              )}
              {result && (
                <>
                  <div className="text-primary-400">└─ Query completed in {(result.execution_time_ms / 1000).toFixed(2)}s</div>
                  <div className="text-gray-500">└─ Pipeline steps: {result.pipeline_steps.length}</div>
                  {result.generated_cypher && (
                    <div className="text-accent-400">└─ Cypher generated ✓</div>
                  )}
                </>
              )}
              <div className="text-gray-600">Type your query above and press Enter</div>
            </div>
          </div>

          {/* Query History */}
          {showHistory && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="glass-card"
            >
              <div className="px-4 py-3 border-b border-surface-700/50">
                <span className="text-xs font-semibold text-white">Recent Queries</span>
              </div>
              <div className="max-h-48 overflow-auto">
                {history.length === 0 ? (
                  <div className="p-4 text-center text-xs text-gray-500">No query history yet</div>
                ) : (
                  history.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => loadFromHistory(item)}
                      className="w-full text-left px-4 py-3 hover:bg-surface-800/50 transition-colors border-b border-surface-700/30 last:border-0"
                    >
                      <p className="text-xs text-gray-300 truncate">{item.natural_query}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] text-gray-500">
                          {item.execution_time_ms ? `${(item.execution_time_ms / 1000).toFixed(1)}s` : ''}
                        </span>
                        <span className={`text-[10px] ${
                          item.status === 'success' ? 'text-emerald-500' : 'text-red-500'
                        }`}>
                          {item.status}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
