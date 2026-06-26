import { useEffect, useState } from 'react';
import { events, createEventWebSocket } from '../services/api';
import SeverityBadge, { StatusBadge } from '../components/SeverityBadge';
import EventSnapshotThumb from '../components/EventSnapshotThumb';
import { format } from 'date-fns';
import { Filter, Volume2 } from 'lucide-react';

export default function EventsPage() {
  const [eventList, setEventList] = useState([]);
  const [filters, setFilters] = useState({ severity: '', status: '' });
  const [loading, setLoading] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(true);

  useEffect(() => {
    loadEvents();
    const ws = createEventWebSocket((msg) => {
      if (msg.type === 'event') {
        setEventList((prev) => [msg.data, ...prev]);
        const playSound =
          msg.data.actions?.sound_alert ||
          ['high', 'critical'].includes(msg.data.severity);
        if (soundEnabled && playSound) {
          playAlert();
        }
      }
    });
    return () => ws.close();
  }, [soundEnabled]);

  const loadEvents = async () => {
    try {
      const params = {};
      if (filters.severity) params.severity = filters.severity;
      if (filters.status) params.status = filters.status;
      const res = await events.list({ ...params, limit: 100 });
      setEventList(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, [filters]);

  const playAlert = () => {
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 800;
      gain.gain.value = 0.1;
      osc.start();
      setTimeout(() => osc.stop(), 200);
    } catch (e) {
      /* ignore */
    }
  };

  const handleStatusChange = async (eventId, newStatus) => {
    await events.update(eventId, { status: newStatus });
    loadEvents();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Eventos</h1>
          <p className="text-gray-400">Panel en tiempo real y modo operador</p>
        </div>
        <button
          onClick={() => setSoundEnabled(!soundEnabled)}
          className={`btn-secondary flex items-center gap-2 ${soundEnabled ? 'text-green-400' : 'text-gray-500'}`}
        >
          <Volume2 className="w-4 h-4" />
          Alerta sonora {soundEnabled ? 'ON' : 'OFF'}
        </button>
      </div>

      <div className="card flex flex-wrap gap-4 items-center">
        <Filter className="w-4 h-4 text-gray-400" />
        <select
          className="input w-auto"
          value={filters.severity}
          onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value }))}
        >
          <option value="">Todas las criticidades</option>
          <option value="critical">Crítica</option>
          <option value="high">Alta</option>
          <option value="medium">Media</option>
          <option value="low">Baja</option>
          <option value="info">Info</option>
        </select>
        <select
          className="input w-auto"
          value={filters.status}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
        >
          <option value="">Todos los estados</option>
          <option value="new">Nuevo</option>
          <option value="seen">Visto</option>
          <option value="in_progress">En proceso</option>
          <option value="escalated">Escalado</option>
          <option value="closed">Cerrado</option>
          <option value="discarded">Descartado</option>
        </select>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b border-dark-700">
              <th className="pb-3 pr-4">Captura</th>
              <th className="pb-3 pr-4">Hora</th>
              <th className="pb-3 pr-4">Evento</th>
              <th className="pb-3 pr-4">Objeto</th>
              <th className="pb-3 pr-4">Criticidad</th>
              <th className="pb-3 pr-4">Estado</th>
              <th className="pb-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="py-8 text-center text-gray-500">Cargando...</td></tr>
            ) : eventList.length === 0 ? (
              <tr><td colSpan={7} className="py-8 text-center text-gray-500">Sin eventos</td></tr>
            ) : (
              eventList.map((evt) => (
                <tr key={evt.id} className="border-b border-dark-700/50 hover:bg-dark-900/50">
                  <td className="py-3 pr-4">
                    <EventSnapshotThumb
                      snapshotUrl={evt.snapshot_url}
                      alt={evt.description || evt.event_type}
                    />
                  </td>
                  <td className="py-3 pr-4 text-gray-400 whitespace-nowrap">
                    {evt.occurred_at && format(new Date(evt.occurred_at), 'HH:mm:ss dd/MM')}
                  </td>
                  <td className="py-3 pr-4">
                    <p className="font-medium">{evt.description || evt.event_type}</p>
                    <p className="text-xs text-gray-500">{evt.event_type}</p>
                  </td>
                  <td className="py-3 pr-4 capitalize">{evt.object_class || '-'}</td>
                  <td className="py-3 pr-4"><SeverityBadge severity={evt.severity} /></td>
                  <td className="py-3 pr-4"><StatusBadge status={evt.status} /></td>
                  <td className="py-3">
                    <select
                      className="input w-auto text-xs py-1"
                      value={evt.status || 'new'}
                      onChange={(e) => handleStatusChange(evt.id, e.target.value)}
                    >
                      <option value="new">Nuevo</option>
                      <option value="seen">Visto</option>
                      <option value="in_progress">En proceso</option>
                      <option value="escalated">Escalado</option>
                      <option value="closed">Cerrado</option>
                      <option value="discarded">Descartado</option>
                    </select>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
