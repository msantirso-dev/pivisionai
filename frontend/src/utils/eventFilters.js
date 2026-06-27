import {
  startOfDay,
  endOfDay,
  subDays,
  subHours,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
} from 'date-fns';

export const DATE_PRESETS = [
  { id: 'all', label: 'Todos' },
  { id: 'today', label: 'Hoy' },
  { id: 'yesterday', label: 'Ayer' },
  { id: 'last24h', label: 'Últimas 24 h' },
  { id: 'week', label: 'Esta semana' },
  { id: 'month', label: 'Este mes' },
  { id: 'custom', label: 'Rango personalizado' },
];

export function getDateRange(preset, customFrom = '', customTo = '') {
  const now = new Date();

  switch (preset) {
    case 'today':
      return {
        date_from: startOfDay(now).toISOString(),
        date_to: endOfDay(now).toISOString(),
      };
    case 'yesterday': {
      const day = subDays(now, 1);
      return {
        date_from: startOfDay(day).toISOString(),
        date_to: endOfDay(day).toISOString(),
      };
    }
    case 'last24h':
      return {
        date_from: subHours(now, 24).toISOString(),
        date_to: now.toISOString(),
      };
    case 'week':
      return {
        date_from: startOfWeek(now, { weekStartsOn: 1 }).toISOString(),
        date_to: endOfWeek(now, { weekStartsOn: 1 }).toISOString(),
      };
    case 'month':
      return {
        date_from: startOfMonth(now).toISOString(),
        date_to: endOfMonth(now).toISOString(),
      };
    case 'custom': {
      const range = {};
      if (customFrom) range.date_from = new Date(customFrom).toISOString();
      if (customTo) range.date_to = new Date(customTo).toISOString();
      return range;
    }
    default:
      return {};
  }
}

export function buildEventQueryParams(filters) {
  const params = { limit: 200 };
  if (filters.severity) params.severity = filters.severity;
  if (filters.status) params.status = filters.status;
  if (filters.camera_id) params.camera_id = filters.camera_id;

  const range = getDateRange(filters.datePreset, filters.dateFrom, filters.dateTo);
  if (range.date_from) params.date_from = range.date_from;
  if (range.date_to) params.date_to = range.date_to;
  return params;
}

export function eventMatchesFilters(evt, filters) {
  if (filters.severity && evt.severity !== filters.severity) return false;
  if (filters.status && evt.status !== filters.status) return false;
  if (filters.camera_id && evt.camera_id !== filters.camera_id) return false;

  if (!evt.occurred_at || filters.datePreset === 'all') return true;

  const range = getDateRange(filters.datePreset, filters.dateFrom, filters.dateTo);
  const ts = new Date(evt.occurred_at).getTime();
  if (range.date_from && ts < new Date(range.date_from).getTime()) return false;
  if (range.date_to && ts > new Date(range.date_to).getTime()) return false;
  return true;
}

export const DEFAULT_EVENT_FILTERS = {
  severity: '',
  status: '',
  camera_id: '',
  datePreset: 'all',
  dateFrom: '',
  dateTo: '',
};
