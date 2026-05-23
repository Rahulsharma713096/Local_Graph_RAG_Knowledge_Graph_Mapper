import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import {
  LayoutDashboard, Network, GitBranch, Cpu, MessageSquare, Boxes,
  ChevronLeft, Menu, Settings, Github,
} from 'lucide-react';
import { clsx } from 'clsx';

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
  { id: 'architecture', label: 'Architecture', icon: Boxes, path: '/architecture' },
  { id: 'pipeline', label: 'Pipeline', icon: GitBranch, path: '/pipeline' },
  { id: 'graph', label: 'Graph View', icon: Network, path: '/graph' },
  { id: 'ollama', label: 'Ollama Models', icon: Cpu, path: '/ollama' },
  { id: 'query', label: 'Query Console', icon: MessageSquare, path: '/query' },
];

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const currentPath = location.pathname.replace('/', '') || 'dashboard';

  return (
    <div className="flex h-screen overflow-hidden bg-surface-950">
      {/* Sidebar */}
      <aside
        className={clsx(
          'flex flex-col border-r border-surface-800 bg-surface-900/50 backdrop-blur-xl transition-all duration-300',
          collapsed ? 'w-16' : 'w-60'
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-16 border-b border-surface-800">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center flex-shrink-0">
            <Network className="w-4 h-4 text-white" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <h1 className="text-sm font-semibold text-white truncate">GraphRAG</h1>
              <p className="text-[10px] text-gray-500 truncate">Knowledge Mapper</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 space-y-1 px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.id;
            return (
              <button
                key={item.id}
                onClick={() => navigate(item.path)}
                className={clsx(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-primary-500/10 text-primary-400 border border-primary-500/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-surface-800/50 border border-transparent'
                )}
                title={item.label}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
                {isActive && !collapsed && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-500" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="p-2 border-t border-surface-800 space-y-1">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 hover:text-gray-300 hover:bg-surface-800/50 transition-all"
          >
            <ChevronLeft className={clsx('w-4 h-4 transition-transform', collapsed && 'rotate-180')} />
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="h-14 border-b border-surface-800 bg-surface-900/30 backdrop-blur-xl flex items-center justify-between px-6 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs text-emerald-400 font-mono">System Online</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="btn-ghost p-2">
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
