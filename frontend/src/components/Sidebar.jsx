import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Camera,
  Video,
  Bell,
  Shield,
  Activity,
  Settings,
  Brain,
  Eye,
} from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/cameras', icon: Camera, label: 'Cámaras' },
  { to: '/live', icon: Video, label: 'En Vivo' },
  { to: '/events', icon: Bell, label: 'Eventos' },
  { to: '/rules', icon: Shield, label: 'Reglas' },
  { to: '/health', icon: Activity, label: 'Salud' },
  { to: '/ai-config', icon: Brain, label: 'IA LLM' },
  { to: '/integrations', icon: Settings, label: 'Integraciones' },
];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-dark-800 border-r border-dark-700 flex flex-col">
      <div className="p-4 border-b border-dark-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-600 rounded-lg flex items-center justify-center">
            <Eye className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg">PI Vision AI</h1>
            <p className="text-xs text-gray-400">Monitoreo Inteligente</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors',
                isActive
                  ? 'bg-primary-600/20 text-primary-400'
                  : 'text-gray-400 hover:bg-dark-700 hover:text-gray-200'
              )
            }
          >
            <Icon className="w-5 h-5" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
