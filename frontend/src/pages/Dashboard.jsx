import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Camera, Bell, Activity, AlertTriangle } from 'lucide-react';
import { cameras, events, health, createEventWebSocket } from '../services/api';
import SeverityBadge from '../components/SeverityBadge';
import EventSnapshotThumb from '../components/EventSnapshotThumb';
import { format } from 'date-fns';

export default function Dashboard() {
  const [stats, setStats] = useState({ cameras: 0, online: 0, events: 0, alerts: 0 });
  const [recentEvents, setRecentEvents] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);

  useEffect(() => {
    loadData();
    const ws = createEventWebSocket((msg) => {
      if (msg.type === 'event') {
        setLiveEvents((prev) => [msg.data, ...prev].slice(0, 10));
        setStats((s) => ({ ...s, events: s.events + 1, alerts: s.alerts + 1 }));
      }
      if (msg.type === 'health') {
        setSystemHealth(msg.data);
      }
    });
    return () => ws.close();
  }, []);

  const loadData = async () => {
    try {
      const [camRes, evtRes, healthRes] = await Promise.all([
        cameras.list(),
        events.list({ limit: 10 }),
        health.system(),
      ]);
      const cams = camRes.data;
      setStats({
        cameras: cams.length,
        online: cams.filter((c) => c.status === 'online').length,
        events: evtRes.data.length,
        alerts: evtRes.data.filter((e) => ['high', 'critical'].includes(e.severity)).length,
      });
      setRecentEvents(evtRes.data);
      setSystemHealth(healthRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  const statCards = [
    { label: 'Cámaras', value: stats.cameras, icon: Camera, color: 'text-blue-400' },
    { label: 'Online', value: stats.online, icon: Activity, color: 'text-green-400' },
    { label: 'Eventos', value: stats.events, icon: Bell, color: 'text-yellow-400' },
    { label: 'Alertas', value: stats.alerts, icon: AlertTriangle, color: 'text-red-400' },
  ];

  const displayEvents = liveEvents.length > 0 ? liveEvents : recentEvents;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-gray-400">Centro de monitoreo en tiempo real</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card flex items-center gap-4">
            <div className={`p-3 rounded-lg bg-dark-700 ${color}`}>
              <Icon className="w-6 h-6" />
            </div>
            <div>
              <p className="text-gray-400 text-sm">{label}</p>
              <p className="text-2xl font-bold">{value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Eventos en Tiempo Real</h2>
            <Link to="/events" className="text-primary-400 text-sm hover:underline">
              Ver todos
            </Link>
          </div>
          <div className="space-y-2">
            {displayEvents.length === 0 ? (
              <p className="text-gray-500 text-center py-8">Sin eventos recientes</p>
            ) : (
              displayEvents.map((evt) => (
                <div
                  key={evt.id}
                  className="flex items-center gap-3 p-3 bg-dark-900 rounded-lg border border-dark-700"
                >
                  <EventSnapshotThumb snapshotUrl={evt.snapshot_url} alt={evt.description} size="sm" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{evt.description || evt.event_type}</p>
                    <p className="text-sm text-gray-400">
                      {evt.object_class && `${evt.object_class} · `}
                      {evt.occurred_at && format(new Date(evt.occurred_at), 'HH:mm:ss dd/MM')}
                    </p>
                  </div>
                  <SeverityBadge severity={evt.severity} />
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Salud del Sistema</h2>
          {systemHealth ? (
            <div className="space-y-3">
              <HealthBar label="CPU" value={systemHealth.cpu_percent} />
              <HealthBar label="RAM" value={systemHealth.ram_percent} />
              {systemHealth.gpu_percent != null && (
                <HealthBar label="GPU" value={systemHealth.gpu_percent} />
              )}
              <HealthBar label="Disco" value={systemHealth.disk_percent} />
              <div className="pt-3 border-t border-dark-700 text-sm space-y-1">
                <p>Cámaras online: <span className="text-green-400">{systemHealth.online_cameras}</span></p>
                <p>Cámaras offline: <span className="text-red-400">{systemHealth.offline_cameras}</span></p>
                <p>Cola IA: {systemHealth.queue_size}</p>
                {systemHealth.degraded_mode && (
                  <p className="text-orange-400 font-medium">Modo degradado activo</p>
                )}
              </div>
            </div>
          ) : (
            <p className="text-gray-500">Cargando...</p>
          )}
        </div>
      </div>
    </div>
  );
}

function HealthBar({ label, value }) {
  const color = value > 85 ? 'bg-red-500' : value > 70 ? 'bg-yellow-500' : 'bg-green-500';
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-400">{label}</span>
        <span>{value?.toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
    </div>
  );
}
