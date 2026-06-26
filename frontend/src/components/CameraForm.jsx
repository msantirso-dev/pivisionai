import { useState } from 'react';
import { X } from 'lucide-react';
import { cameras } from '../services/api';

export default function CameraForm({ onClose, onSaved }) {
  const [form, setForm] = useState({
    name: '',
    location: '',
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
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : type === 'number' ? Number(value) : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await cameras.create(form);
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al crear cámara');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Nueva Cámara Dahua</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 px-3 py-2 rounded-lg text-sm mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-sm text-gray-400">Nombre</label>
              <input name="name" className="input" value={form.name} onChange={handleChange} required />
            </div>
            <div className="col-span-2">
              <label className="text-sm text-gray-400">Ubicación</label>
              <input name="location" className="input" value={form.location} onChange={handleChange} />
            </div>
            <div>
              <label className="text-sm text-gray-400">IP</label>
              <input name="ip_address" className="input" value={form.ip_address} onChange={handleChange} required />
            </div>
            <div>
              <label className="text-sm text-gray-400">Puerto RTSP</label>
              <input name="port" type="number" className="input" value={form.port} onChange={handleChange} />
            </div>
            <div>
              <label className="text-sm text-gray-400">Usuario</label>
              <input name="username" className="input" value={form.username} onChange={handleChange} required />
            </div>
            <div>
              <label className="text-sm text-gray-400">Contraseña</label>
              <input name="password" type="password" className="input" value={form.password} onChange={handleChange} required />
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
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="dahua_api_enabled" checked={form.dahua_api_enabled} onChange={handleChange} />
              API Dahua IVS
            </label>
          </div>

          <p className="text-xs text-gray-500">
            Las URLs RTSP se generan automáticamente para cámaras Dahua.
          </p>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Cancelar</button>
            <button type="submit" className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
