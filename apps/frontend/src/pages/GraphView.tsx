import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Network, Search, ZoomIn, ZoomOut, RotateCw, Code2, BarChart3, Maximize2 } from 'lucide-react';
import cytoscape from 'cytoscape';
import * as api from '../lib/api';
import type { GraphData } from '../types';

export function GraphView() {
  const cyRef = useRef<HTMLDivElement>(null);
  const cyInstance = useRef<cytoscape.Core | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState<Record<string, any>>({});
  const [cypherQuery, setCypherQuery] = useState('');
  const [cypherResult, setCypherResult] = useState<string>('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [showCypher, setShowCypher] = useState(false);

  useEffect(() => {
    loadGraph();
  }, []);

  useEffect(() => {
    if (graphData && cyRef.current) {
      initCytoscape();
    }
  }, [graphData]);

  const loadGraph = async () => {
    setLoading(true);
    try {
      const data = await api.getGraph(100);
      const graphStats = await api.getGraphStats();
      setGraphData(data);
      setStats(graphStats);
    } catch (e) {
      console.error('Failed to load graph', e);
    } finally {
      setLoading(false);
    }
  };

  const initCytoscape = () => {
    if (!cyRef.current || !graphData) return;

    if (cyInstance.current) {
      cyInstance.current.destroy();
    }

    const elements = [
      ...graphData.nodes.map((node) => ({
        data: {
          id: node.id,
          label: node.name || node.id,
          type: node.label,
        },
        classes: node.label?.toLowerCase() || 'node',
      })),
      ...graphData.edges.map((edge) => ({
        data: {
          id: `${edge.source}-${edge.target}-${edge.relationship}`,
          source: edge.source,
          target: edge.target,
          label: edge.relationship,
        },
      })),
    ];

    if (elements.length === 0) {
      // Add demo elements if empty
      elements.push(
        { data: { id: 'customer1', label: 'Alice Johnson', type: 'Customer' }, classes: 'customer' },
        { data: { id: 'customer2', label: 'Bob Smith', type: 'Customer' }, classes: 'customer' },
        { data: { id: 'product1', label: 'Laptop Pro', type: 'Product' }, classes: 'product' },
        { data: { id: 'product2', label: 'Wireless Mouse', type: 'Product' }, classes: 'product' },
        { data: { id: 'order1', label: 'ORD-001', type: 'Order' }, classes: 'order' },
        { data: { id: 'supplier1', label: 'TechSupply Co', type: 'Supplier' }, classes: 'supplier' },
        { data: { id: 'order1-customer1', source: 'order1', target: 'customer1', label: 'PLACED_BY' } },
        { data: { id: 'order1-product1', source: 'order1', target: 'product1', label: 'INCLUDES' } },
        { data: { id: 'customer1-product1', source: 'customer1', target: 'product1', label: 'PURCHASED' } },
        { data: { id: 'customer2-product2', source: 'customer2', target: 'product2', label: 'PURCHASED' } },
        { data: { id: 'supplier1-product1', source: 'supplier1', target: 'product1', label: 'SUPPLIES' } },
      );
    }

    cyInstance.current = cytoscape({
      container: cyRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#6366f1',
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            color: '#94a3b8',
            'font-size': '11px',
            'text-margin-y': 8,
            width: 'mapData(weight, 0, 100, 20, 60)',
            height: 'mapData(weight, 0, 100, 20, 60)',
            'border-width': 2,
            'border-color': '#334155',
          },
        },
        {
          selector: 'node.customer',
          style: { 'background-color': '#6366f1', 'border-color': '#818cf8' },
        },
        {
          selector: 'node.product',
          style: { 'background-color': '#14b8a6', 'border-color': '#2dd4bf' },
        },
        {
          selector: 'node.order',
          style: { 'background-color': '#f59e0b', 'border-color': '#fbbf24' },
        },
        {
          selector: 'node.supplier',
          style: { 'background-color': '#ef4444', 'border-color': '#f87171' },
        },
        {
          selector: 'node.employee',
          style: { 'background-color': '#8b5cf6', 'border-color': '#a78bfa' },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': '#475569',
            'target-arrow-color': '#475569',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': '9px',
            color: '#64748b',
            'text-rotation': 'autorotate',
            'text-margin-x': 5,
          },
        },
        {
          selector: ':selected',
          style: {
            'border-width': 3,
            'border-color': '#a5b4fc',
            'shadow-blur': 20,
            'shadow-color': '#6366f1',
            'shadow-opacity': 0.5,
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 1000,
        gravity: 0.8,
        numIter: 1000,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      minZoom: 0.2,
      maxZoom: 5,
    });

    // Event handlers
    cyInstance.current.on('tap', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode({
        id: node.id(),
        label: node.data('label'),
        type: node.data('type'),
      });
    });

    cyInstance.current.on('tap', (evt) => {
      if (evt.target === cyInstance.current) {
        setSelectedNode(null);
      }
    });
  };

  const handleZoomIn = () => cyInstance.current?.zoom(cyInstance.current.zoom() * 1.3);
  const handleZoomOut = () => cyInstance.current?.zoom(cyInstance.current.zoom() / 1.3);
  const handleFit = () => cyInstance.current?.fit(undefined, 50);
  const handleRefresh = () => loadGraph();

  const handleCypherExecute = async () => {
    try {
      const result = await api.executeCypher(cypherQuery);
      setCypherResult(JSON.stringify(result, null, 2));
    } catch (e: any) {
      setCypherResult(`Error: ${e.message}`);
    }
  };

  const handleSearch = () => {
    if (!cyInstance.current || !searchQuery) return;
    cyInstance.current.elements().unselect();
    const matching = cyInstance.current.nodes(`[label *= "${searchQuery}"]`);
    if (matching.length > 0) {
      matching.select();
      cyInstance.current.animate({
        fit: {
          eles: matching,
          padding: 80,
        },
        duration: 500,
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RotateCw className="w-6 h-6 text-primary-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Knowledge Graph</h1>
          <p className="text-sm text-gray-500 mt-1">Interactive graph visualization and exploration</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Toolbar + Graph */}
        <div className="lg:col-span-3 space-y-4">
          {/* Toolbar */}
          <div className="glass-card p-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button onClick={handleZoomIn} className="btn-ghost p-2" title="Zoom In">
                <ZoomIn className="w-4 h-4" />
              </button>
              <button onClick={handleZoomOut} className="btn-ghost p-2" title="Zoom Out">
                <ZoomOut className="w-4 h-4" />
              </button>
              <button onClick={handleFit} className="btn-ghost p-2" title="Fit Graph">
                <Maximize2 className="w-4 h-4" />
              </button>
              <button onClick={handleRefresh} className="btn-ghost p-2" title="Refresh">
                <RotateCw className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center gap-2 flex-1 max-w-md mx-4">
              <Search className="w-4 h-4 text-gray-500" />
              <input
                className="input-field py-1.5 text-sm"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search nodes..."
              />
            </div>

            <button
              onClick={() => setShowCypher(!showCypher)}
              className={`btn-ghost p-2 ${showCypher ? 'text-primary-400' : ''}`}
              title="Cypher Query"
            >
              <Code2 className="w-4 h-4" />
            </button>
          </div>

          {/* Graph Canvas */}
          <div className="glass-card overflow-hidden" style={{ height: '500px' }}>
            <div ref={cyRef} id="cy" className="w-full h-full" />
            {(!graphData || (graphData.nodes.length === 0 && !cyInstance.current)) && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center text-gray-500">
                  <Network className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No graph data available</p>
                  <p className="text-xs mt-1">Run a pipeline or seed demo data to populate the graph</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Side Panel */}
        <div className="space-y-4">
          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="glass-card p-4"
          >
            <h3 className="text-xs font-semibold text-white mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-primary-400" />
              Graph Statistics
            </h3>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Nodes</span>
                <span className="text-white font-bold">{stats?.node_count || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Edges</span>
                <span className="text-white font-bold">{stats?.edge_count || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Node Types</span>
                <span className="text-white font-bold">{stats?.node_labels?.length || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Relationships</span>
                <span className="text-white font-bold">{stats?.relationship_types?.length || 0}</span>
              </div>
            </div>
          </motion.div>

          {/* Selected Node */}
          {selectedNode && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-4"
            >
              <h3 className="text-xs font-semibold text-white mb-3">Selected Node</h3>
              <div className="space-y-2">
                <div className="text-xs"><span className="text-gray-500">Name:</span> <span className="text-gray-200">{selectedNode.label}</span></div>
                <div className="text-xs"><span className="text-gray-500">Type:</span> <span className="badge-primary text-[10px]">{selectedNode.type}</span></div>
                <div className="text-xs"><span className="text-gray-500">ID:</span> <span className="text-gray-400 font-mono">{selectedNode.id}</span></div>
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* Cypher Query Panel */}
      {showCypher && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4"
        >
          <h3 className="text-sm font-semibold text-white mb-3">Cypher Query</h3>
          <div className="flex gap-3">
            <input
              className="input-field flex-1 font-mono text-sm"
              value={cypherQuery}
              onChange={(e) => setCypherQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCypherExecute()}
              placeholder="MATCH (n) RETURN n LIMIT 25"
            />
            <button onClick={handleCypherExecute} className="btn-primary">Run</button>
          </div>
          {cypherResult && (
            <pre className="mt-3 p-3 bg-surface-900 rounded-lg text-xs text-gray-400 font-mono overflow-auto max-h-40">
              {cypherResult}
            </pre>
          )}
        </motion.div>
      )}
    </div>
  );
}
