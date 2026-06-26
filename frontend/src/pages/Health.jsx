import { useEffect, useState } from 'react';
import { health } from '../services/api';
import { RefreshCw } from 'lucide-react';

export default function HealthPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadHealth = async () => {
    setLoading(true);
    try {
      const res = await health.system();
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
    const interval = setInterval(loadHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return <p className="text-gray-500">Cargando salud del sistema...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Salud del Sistema</h1>
          <p className="text-gray-400">Monitoreo de recursos y cámaras (hasta 128 canales)</p>
        </div>
        <button onClick={loadHealth} className="btn-secondary flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Actualizar
        </button>
      </div>

      {data?.degraded_mode && (
        <div className="bg-orange-900/30 border border-orange-700 text-orange-300 px-4 py-3 rounded-lg">
          Modo degradado activo — el sistema reduce carga de IA automáticamente.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="CPU" value={`${data?.cpu_percent?.toFixed(1)}%`} warn={data?.cpu_percent > 85} />
        <MetricCard label="RAM" value={`${data?.ram_percent?.toFixed(1)}%`} warn={data?.ram_percent > 85} />
        <MetricCard label="GPU" value={data?.gpu_percent != null ? `${data.gpu_percent.toFixed(1)}%` : 'N/A'} warn={data?.gpu_percent > 90} />
        <MetricCard label="Disco" value={`${data?.disk_percent?.toFixed(1)}%`} warn={data?.disk_percent > 90} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <h3 className="font-semibold mb-3">Cámaras</h3>
          <div className="space-y-2 text-sm">
            <p>Online: <span className="text-green-400 font-bold">{data?.online_cameras}</span></p>
            <p>Offline: <span className="text-gray-400 font-bold">{data?.offline_cameras}</span></p>
            <p>Errores: <span className="text-red-400 font-bold">{data?.error_cameras}</span></p>
          </div>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-3">Workers</h3>
          <div className="space-y-2 text-sm">
            <p>Activos: {data?.active_workers}</p>
            <p>Cola IA: {data?.queue_size}</p>
            <p>VRAM: {data?.vram_percent != null ? `${data.vram_percent.toFixed(1)}%` : 'N/A'}</p>
          </div>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-3">Red</h3>
          <p className="text-sm">Tráfico acumulado: {data?.network_mbps?.toFixed(1) || 0} MB</p>
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-4">Estado por Cámara</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-400 border-b border-dark-700">
                <th className="pb-2 pr-4">Nombre</th>
                <th className="pb-2 pr-4">IP</th>
                <th className="pb-2 pr-4">Estado</th>
                <th className="pb-2 pr-4">IA</th>
                <th className="pb-2">Última conexión</th>
              </tr>
            </thead>
            <tbody>
              {(data?.cameras || []).map((cam) => (
                <tr key={cam.id} className="border-b border-dark-700/50">
                  <td className="py-2 pr-4">{cam.name}</td>
                  <td className="py-2 pr-4 text-gray-400">{cam.ip_address}</td>
                  <td className="py-2 pr-4 capitalize">
                    <span className={cam.status === 'online' ? 'text-green-400' : cam.status === 'error' ? 'text-red-400' : 'text-gray-400'}>
                      {cam.status}
                    </span>
                  </td>
                  <td className="py-2 pr-4">{cam.ai_enabled ? 'Sí' : 'No'}</td>
                  <td className="py-2 text-gray-400">{cam.last_seen_at ? new Date(cam.last_seen_at).toLocaleString() : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, warn }) {
  return (
    <div className={`card ${warn ? 'border-orange-600' : ''}`}>
      <p className="text-gray-400 text-sm">{label}</p>
      <p className={`text-2xl font-bold ${warn ? 'text-orange-400' : ''}`}>{value}</p>
    </div>
  );
}
