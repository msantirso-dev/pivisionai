import { useEffect, useState } from 'react';
import { X, Cloud, Wifi } from 'lucide-react';
import { cameras } from '../services/api';

const DEFAULT_FORM = {
  name: '',
  location: '',
  connection_mode: 'local',
  device_serial: '',
  ip_address: '',
  port: 554,
  username: 'admin',
  password: '',
  brand: 'dahua',
  channel: 1,
  ai_enabled: true,
  ai_fps: 5,
  ai_confidence: 0.45,
  dahua_api_enabled: true,
  dahua_api_port: 80,
};

export default function CameraForm({ onClose, onSaved }) {
  const [form, setForm] = useState({ ...DEFAULT_FORM });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [cloudStatus, setCloudStatus] = useState(null);

  const isCloud = form.connection_mode === 'cloud';

  useEffect(() => {
    cameras.cloudStatus().then((res) => setCloudStatus(res.data)).catch(() => {});
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : type === 'number' ? Number(value) : value,
    }));
  };

  const setConnectionMode = (mode) => {
    setForm((prev) => ({
      ...prev,
      connection_mode: mode,
      dahua_api_enabled: mode === 'local',
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const payload = { ...form };
    if (isCloud) {
      payload.device_serial = form.device_serial.trim();
      payload.ip_address = null;
      payload.dahua_api_enabled = false;
    } else {
      payload.device_serial = null;
      payload.ip_address = form.ip_address.trim();
    }

    try {
      await cameras.create(payload);
      onSaved();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join(', '));
      } else {
        setError('Error al crear cámara');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Nueva Cámara Dahua</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 px-3 py-2 rounded-lg text-sm mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="p-3 rounded-lg border border-primary-700/50 bg-primary-950/40">
            <label htmlFor="connection_mode" className="text-sm font-medium text-gray-200 mb-2 block">
              Tipo de conexión
            </label>
            <select
              id="connection_mode"
              name="connection_mode"
              className="input mb-3"
              value={form.connection_mode}
              onChange={(e) => setConnectionMode(e.target.value)}
            >
              <option value="local">IP local (LAN) — red local o VPN</option>
              <option value="cloud">Nube Dahua — número de serie (Lechange/Imou)</option>
            </select>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setConnectionMode('local')}
                className={`p-3 rounded-lg border text-left transition-colors ${
                  !isCloud
                    ? 'border-primary-500 bg-primary-900/30'
                    : 'border-dark-600 hover:border-dark-500'
                }`}
              >
                <Wifi className="w-4 h-4 mb-1 text-primary-400" />
                <span className="block text-sm font-medium">IP local (LAN)</span>
                <span className="block text-xs text-gray-500">Red local / VPN</span>
              </button>
              <button
                type="button"
                onClick={() => setConnectionMode('cloud')}
                className={`p-3 rounded-lg border text-left transition-colors ${
                  isCloud
                    ? 'border-primary-500 bg-primary-900/30'
                    : 'border-dark-600 hover:border-dark-500'
                }`}
              >
                <Cloud className="w-4 h-4 mb-1 text-primary-400" />
                <span className="block text-sm font-medium">Nube (serial)</span>
                <span className="block text-xs text-gray-500">Lechange / Imou API</span>
              </button>
            </div>
            {isCloud && cloudStatus && !cloudStatus.configured && (
              <p className="text-xs text-amber-400 mt-2">
                Cloud no configurado en el servidor. Defina DAHUA_CLOUD_APP_ID y DAHUA_CLOUD_APP_SECRET en .env
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-sm text-gray-400">Nombre</label>
              <input name="name" className="input" value={form.name} onChange={handleChange} required />
            </div>
            <div className="col-span-2">
              <label className="text-sm text-gray-400">Ubicación</label>
              <input name="location" className="input" value={form.location} onChange={handleChange} />
            </div>

            {isCloud ? (
              <div className="col-span-2">
                <label className="text-sm text-gray-400">Número de serie del dispositivo</label>
                <input
                  name="device_serial"
                  className="input font-mono"
                  value={form.device_serial}
                  onChange={handleChange}
                  placeholder="Ej: 8L0123456789ABCDE"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">
                  Etiqueta en la cámara o app Imou/DMSS. La contraseña es la del dispositivo.
                </p>
              </div>
            ) : (
              <>
                <div>
                  <label className="text-sm text-gray-400">IP</label>
                  <input
                    name="ip_address"
                    className="input"
                    value={form.ip_address}
                    onChange={handleChange}
                    placeholder="192.168.1.100"
                    required
                  />
                </div>
                <div>
                  <label className="text-sm text-gray-400">Puerto RTSP</label>
                  <input name="port" type="number" className="input" value={form.port} onChange={handleChange} />
                </div>
              </>
            )}

            <div>
              <label className="text-sm text-gray-400">Usuario</label>
              <input name="username" className="input" value={form.username} onChange={handleChange} required />
            </div>
            <div>
              <label className="text-sm text-gray-400">Contraseña del dispositivo</label>
              <input
                name="password"
                type="password"
                className="input"
                value={form.password}
                onChange={handleChange}
                required
              />
            </div>
            <div>
              <label className="text-sm text-gray-400">Canal</label>
              <input name="channel" type="number" className="input" value={form.channel} onChange={handleChange} />
            </div>
            <div>
              <label className="text-sm text-gray-400">FPS IA</label>
              <input name="ai_fps" type="number" className="input" value={form.ai_fps} onChange={handleChange} />
            </div>
          </div>

          <div className="flex gap-4 pt-2">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="ai_enabled" checked={form.ai_enabled} onChange={handleChange} />
              Análisis IA activo
            </label>
            {!isCloud && (
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  name="dahua_api_enabled"
                  checked={form.dahua_api_enabled}
                  onChange={handleChange}
                />
                API Dahua IVS (local)
              </label>
            )}
          </div>

          <p className="text-xs text-gray-500">
            {isCloud
              ? 'La captura usa la API cloud Lechange/Imou. IVS local no aplica en modo nube.'
              : 'Las URLs RTSP se generan automáticamente para cámaras Dahua en red local.'}
          </p>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">
              Cancelar
            </button>
            <button type="submit" className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
