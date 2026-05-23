import { motion } from 'framer-motion';
import {
  Database, GitBranch, Share2, Brain, Search, Cpu, LayoutDashboard,
  ArrowRight, ArrowDown, Server, Globe,
} from 'lucide-react';

const layers = [
  {
    title: 'Data Sources',
    icon: Database,
    color: 'from-blue-500 to-blue-600',
    items: ['PostgreSQL', 'MySQL', 'SQLite', 'CSV Files'],
    description: 'Connect and ingest from multiple data sources',
  },
  {
    title: 'ETL Pipeline',
    icon: GitBranch,
    color: 'from-purple-500 to-purple-600',
    items: ['Extract', 'Normalize', 'Clean', 'Transform'],
    description: 'Extract, normalize and prepare data for graph construction',
  },
  {
    title: 'Knowledge Graph',
    icon: Share2,
    color: 'from-emerald-500 to-emerald-600',
    items: ['Neo4j Nodes', 'Relationships', 'Properties', 'Communities'],
    description: 'Build and store entity-relationship knowledge graph',
  },
  {
    title: 'Embeddings & Vectors',
    icon: Brain,
    color: 'from-amber-500 to-amber-600',
    items: ['sentence-transformers', 'FAISS Index', 'Vector Search', 'Semantic Search'],
    description: 'Generate embeddings and build vector index for similarity search',
  },
  {
    title: 'RAG Engine',
    icon: Search,
    color: 'from-rose-500 to-rose-600',
    items: ['Graph Context', 'Vector Retrieval', 'Cypher Generation', 'Answer Synthesis'],
    description: 'Retrieve graph-aware context and generate answers',
  },
  {
    title: 'LLM Inference',
    icon: Cpu,
    color: 'from-cyan-500 to-cyan-600',
    items: ['Ollama', 'llama3.1', 'mistral', 'phi3'],
    description: 'Local inference with Ollama - buffered for performance',
  },
  {
    title: 'Dashboard UI',
    icon: LayoutDashboard,
    color: 'from-indigo-500 to-indigo-600',
    items: ['React + TypeScript', 'TailwindCSS', 'Cytoscape.js', 'Recharts'],
    description: 'Interactive real-time visualization and control interface',
  },
];

const techStack = [
  { name: 'FastAPI', category: 'Backend' },
  { name: 'React', category: 'Frontend' },
  { name: 'Neo4j', category: 'Database' },
  { name: 'FAISS', category: 'Vectors' },
  { name: 'Ollama', category: 'LLM' },
  { name: 'Docker', category: 'Infra' },
  { name: 'WebSocket', category: 'Realtime' },
  { name: 'spaCy', category: 'NLP' },
];

export function Architecture() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">System Architecture</h1>
        <p className="text-sm text-gray-500 mt-1">End-to-end data flow from ingestion to visualization</p>
      </div>

      {/* Flow Diagram */}
      <div className="relative">
        <div className="hidden lg:flex items-center justify-between gap-2">
          {layers.map((layer, index) => {
            const Icon = layer.icon;
            return (
              <motion.div
                key={layer.title}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex-1"
              >
                <div className={`glass-card-hover p-4 text-center relative group`}>
                  {/* Arrow connector */}
                  {index < layers.length - 1 && (
                    <div className="absolute -right-4 top-1/2 -translate-y-1/2 z-10">
                      <ArrowRight className="w-4 h-4 text-primary-500 animate-pulse" />
                    </div>
                  )}

                  <div className={`w-10 h-10 mx-auto mb-3 rounded-lg bg-gradient-to-br ${layer.color} flex items-center justify-center`}>
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  <h3 className="text-xs font-semibold text-white mb-1">{layer.title}</h3>
                  <ul className="space-y-0.5">
                    {layer.items.slice(0, 3).map((item) => (
                      <li key={item} className="text-[10px] text-gray-500">{item}</li>
                    ))}
                  </ul>
                  {/* Tooltip */}
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-xs text-gray-300 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-xl">
                    {layer.description}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Mobile: Vertical Stack */}
        <div className="lg:hidden space-y-4">
          {layers.map((layer, index) => {
            const Icon = layer.icon;
            return (
              <motion.div
                key={layer.title}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="glass-card-hover p-4 flex items-center gap-4"
              >
                <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${layer.color} flex items-center justify-center flex-shrink-0`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-white">{layer.title}</h3>
                  <p className="text-xs text-gray-500 truncate">{layer.description}</p>
                </div>
                {index < layers.length - 1 && <ArrowDown className="w-4 h-4 text-primary-500 flex-shrink-0" />}
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Tech Stack Tags */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7 }}
        className="glass-card p-5"
      >
        <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
          <Server className="w-4 h-4 text-primary-400" />
          Technology Stack
        </h2>
        <div className="flex flex-wrap gap-2">
          {techStack.map((tech) => (
            <span
              key={tech.name}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-primary-500/5 text-primary-300 border border-primary-500/20 hover:bg-primary-500/10 transition-colors"
            >
              {tech.name}
              <span className="text-[10px] text-gray-500">({tech.category})</span>
            </span>
          ))}
        </div>
      </motion.div>

      {/* Description */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="glass-card p-5"
      >
        <h2 className="text-sm font-semibold text-white mb-3">Data Flow</h2>
        <div className="text-sm text-gray-400 leading-relaxed">
          <p>
            <span className="text-primary-400 font-medium">SQL/CSV</span> data sources are ingested through the{' '}
            <span className="text-purple-400 font-medium">ETL Pipeline</span>, which extracts entities and relationships
            to build a <span className="text-emerald-400 font-medium">Neo4j Knowledge Graph</span>.
            <span className="text-amber-400 font-medium"> sentence-transformers</span> generate embeddings indexed in{' '}
            <span className="text-amber-400 font-medium">FAISS</span> for vector search.
          </p>
          <p className="mt-2">
            The <span className="text-rose-400 font-medium">RAG Engine</span> performs hybrid graph+vector retrieval,
            generates Cypher queries, traverses the graph, and sends context to{' '}
            <span className="text-cyan-400 font-medium">Ollama</span> for final answer generation.
            Results stream back to the <span className="text-indigo-400 font-medium">real-time dashboard</span>.
          </p>
        </div>
      </motion.div>
    </div>
  );
}
