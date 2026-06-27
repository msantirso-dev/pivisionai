import { useEffect, useState, useMemo } from 'react';
import { events, cameras, createEventWebSocket } from '../services/api';
import SeverityBadge, { StatusBadge } from '../components/SeverityBadge';
import EventSnapshotThumb from '../components/EventSnapshotThumb';
import EventReviewText from '../components/EventReviewText';
import { mergeEventUpdate } from '../utils/eventReview';
import {
  DATE_PRESETS,
  DEFAULT_EVENT_FILTERS,
  buildEventQueryParams,
  eventMatchesFilters,
} from '../utils/eventFilters';
import { format } from 'date-fns';
import { Filter, Volume2, X, Calendar, CheckSquare, Square } from 'lucide-react';

const EVENT_STATUSES = [
  { value: 'new', label: 'Nuevo' },
  { value: 'seen', label: 'Visto' },
  { value: 'in_progress', label: 'En proceso' },
  { value: 'escalated', label: 'Escalado' },
  { value: 'closed', label: 'Cerrado' },
  { value: 'discarded', label: 'Descartado' },
];

const QUICK_BULK_ACTIONS = [
  { status: 'seen', label: 'Marcar vistos' },
  { status: 'closed', label: 'Cerrar' },
  { status: 'discarded', label: 'Descartar' },
];

export default function EventsPage() {
  const [eventList, setEventList] = useState([]);
  const [cameraList, setCameraList] = useState([]);
  const [filters, setFilters] = useState({ ...DEFAULT_EVENT_FILTERS });
  const [loading, setLoading] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkStatus, setBulkStatus] = useState('seen');
  const [bulkComment, setBulkComment] = useState('');
  const [bulkApplying, setBulkApplying] = useState(false);

  const hasActiveFilters = useMemo(
    () => JSON.stringify(filters) !== JSON.stringify(DEFAULT_EVENT_FILTERS),
    [filters]
  );

  useEffect(() => {
    cameras.list().then((res) => setCameraList(res.data || [])).catch(() => {});
  }, []);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const res = await events.list(buildEventQueryParams(filters));
      setEventList(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
    setSelectedIds(new Set());
  }, [filters]);

  useEffect(() => {
    const ws = createEventWebSocket((msg) => {
      if (msg.type !== 'event') return;

      setEventList((prev) => {
        const isNew = !prev.some((e) => e.id === msg.data.id);
        let merged = mergeEventUpdate(prev, msg.data);

        if (isNew && !msg.data.llm_updated && !eventMatchesFilters(msg.data, filters)) {
          return prev;
        }

        if (!isNew && msg.data.llm_updated && !eventMatchesFilters(msg.data, filters)) {
          return prev.filter((e) => e.id !== msg.data.id);
        }

        if (isNew && !msg.data.llm_updated) {
          const playSound =
            msg.data.actions?.sound_alert ||
            ['high', 'critical'].includes(msg.data.severity);
          if (soundEnabled && playSound) playAlert();
        }

        return merged;
      });
    });
    return () => ws.close();
  }, [soundEnabled, filters]);

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

  const allVisibleSelected =
    eventList.length > 0 && eventList.every((evt) => selectedIds.has(evt.id));
  const someSelected = selectedIds.size > 0;

  const toggleSelectAll = () => {
    if (allVisibleSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(eventList.map((evt) => evt.id)));
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const applyBulkAction = async (status, ids = null) => {
    const targetIds = ids ?? (selectedIds.size > 0 ? [...selectedIds] : eventList.map((e) => e.id));
    if (!targetIds.length) return;

    setBulkApplying(true);
    try {
      await events.bulkUpdate({
        event_ids: targetIds,
        status,
        comment: bulkComment.trim() || undefined,
      });
      setSelectedIds(new Set());
      setBulkComment('');
      await loadEvents();
    } catch (err) {
      console.error(err);
      alert('No se pudo aplicar la acción al grupo de eventos');
    } finally {
      setBulkApplying(false);
    }
  };

  const applyToSelectionOrVisible = (status) => {
    const ids = someSelected ? [...selectedIds] : eventList.map((e) => e.id);
    applyBulkAction(status, ids);
  };

  const clearFilters = () => setFilters({ ...DEFAULT_EVENT_FILTERS });

  const setPreset = (preset) => {
    setFilters((f) => ({
      ...f,
      datePreset: preset,
      ...(preset !== 'custom' ? { dateFrom: '', dateTo: '' } : {}),
    }));
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

      <div className="card space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400 shrink-0" />
          <Calendar className="w-4 h-4 text-gray-400 shrink-0" />
          {DATE_PRESETS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setPreset(id)}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                filters.datePreset === id
                  ? 'bg-primary-600/30 border-primary-500 text-primary-300'
                  : 'border-dark-600 text-gray-400 hover:border-dark-500'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {filters.datePreset === 'custom' && (
          <div className="flex flex-wrap gap-4 items-end pt-2 border-t border-dark-700">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Desde (día, hora, minuto)</label>
              <input
                type="datetime-local"
                className="input text-sm"
                value={filters.dateFrom}
                onChange={(e) => setFilters((f) => ({ ...f, dateFrom: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Hasta (día, hora, minuto)</label>
              <input
                type="datetime-local"
                className="input text-sm"
                value={filters.dateTo}
                onChange={(e) => setFilters((f) => ({ ...f, dateTo: e.target.value }))}
              />
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-4 items-center pt-2 border-t border-dark-700">
          <select
            className="input w-auto text-sm"
            value={filters.camera_id}
            onChange={(e) => setFilters((f) => ({ ...f, camera_id: e.target.value }))}
          >
            <option value="">Todas las cámaras</option>
            {cameraList.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <select
            className="input w-auto text-sm"
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
            className="input w-auto text-sm"
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

          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="btn-secondary text-sm flex items-center gap-1"
            >
              <X className="w-3 h-3" /> Limpiar filtros
            </button>
          )}

          <span className="text-xs text-gray-500 ml-auto">
            {loading ? 'Cargando…' : `${eventList.length} evento(s)`}
          </span>
        </div>
      </div>

      {!loading && eventList.length > 0 && (
        <div className="card flex flex-wrap items-center gap-3 border-primary-500/30 bg-dark-900/80">
          <button
            type="button"
            onClick={toggleSelectAll}
            className="btn-secondary text-sm flex items-center gap-2"
          >
            {allVisibleSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
            {allVisibleSelected ? 'Deseleccionar todos' : 'Seleccionar visibles'}
          </button>

          <span className="text-sm text-gray-400">
            {someSelected ? `${selectedIds.size} seleccionado(s)` : 'Sin selección — acciones aplican a todos los visibles'}
          </span>

          <div className="flex flex-wrap gap-2">
            {QUICK_BULK_ACTIONS.map(({ status, label }) => (
              <button
                key={status}
                type="button"
                disabled={bulkApplying}
                onClick={() => applyToSelectionOrVisible(status)}
                className="btn-secondary text-xs"
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2 ml-auto">
            <select
              className="input w-auto text-sm py-1"
              value={bulkStatus}
              onChange={(e) => setBulkStatus(e.target.value)}
            >
              {EVENT_STATUSES.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <input
              className="input text-sm w-48"
              placeholder="Comentario (opcional)"
              value={bulkComment}
              onChange={(e) => setBulkComment(e.target.value)}
            />
            <button
              type="button"
              disabled={bulkApplying || (!someSelected && eventList.length === 0)}
              onClick={() => applyBulkAction(bulkStatus)}
              className="btn-primary text-sm"
            >
              {bulkApplying
                ? 'Aplicando…'
                : someSelected
                  ? `Aplicar a ${selectedIds.size}`
                  : `Aplicar a ${eventList.length} visibles`}
            </button>
            {someSelected && (
              <button
                type="button"
                onClick={() => setSelectedIds(new Set())}
                className="btn-secondary text-sm"
              >
                Limpiar
              </button>
            )}
          </div>
        </div>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b border-dark-700">
              <th className="pb-3 pr-2 w-10">
                <input
                  type="checkbox"
                  checked={allVisibleSelected && eventList.length > 0}
                  onChange={toggleSelectAll}
                  title="Seleccionar todos los visibles"
                />
              </th>
              <th className="pb-3 pr-4">Captura</th>
              <th className="pb-3 pr-4">Fecha y hora</th>
              <th className="pb-3 pr-4">Reseña de la imagen</th>
              <th className="pb-3 pr-4">Objeto</th>
              <th className="pb-3 pr-4">Criticidad</th>
              <th className="pb-3 pr-4">Estado</th>
              <th className="pb-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="py-8 text-center text-gray-500">Cargando...</td></tr>
            ) : eventList.length === 0 ? (
              <tr><td colSpan={8} className="py-8 text-center text-gray-500">Sin eventos para los filtros seleccionados</td></tr>
            ) : (
              eventList.map((evt) => (
                <tr
                  key={evt.id}
                  className={`border-b border-dark-700/50 hover:bg-dark-900/50 ${
                    selectedIds.has(evt.id) ? 'bg-primary-900/20' : ''
                  }`}
                >
                  <td className="py-3 pr-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(evt.id)}
                      onChange={() => toggleSelect(evt.id)}
                    />
                  </td>
                  <td className="py-3 pr-4">
                    <EventSnapshotThumb
                      snapshotUrl={evt.snapshot_url}
                      alt={evt.description || evt.event_type}
                      size="lg"
                      event={evt}
                    />
                  </td>
                  <td className="py-3 pr-4 text-gray-400 whitespace-nowrap">
                    {evt.occurred_at && (
                      <>
                        <span className="block">{format(new Date(evt.occurred_at), 'dd/MM/yyyy')}</span>
                        <span className="block text-xs">{format(new Date(evt.occurred_at), 'HH:mm:ss')}</span>
                      </>
                    )}
                  </td>
                  <td className="py-3 pr-4">
                    <EventReviewText event={evt} />
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
                      {EVENT_STATUSES.map(({ value, label }) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
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
