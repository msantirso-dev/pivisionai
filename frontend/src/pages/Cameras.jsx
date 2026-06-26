import { useEffect, useState } from 'react';
import { Plus, Wifi, Camera as CameraIcon, Trash2 } from 'lucide-react';
import { cameras } from '../services/api';
import CameraForm from '../components/CameraForm';

export default function CamerasPage() {
  const [cameraList, setCameraList] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCameras();
  }, []);

  const loadCameras = async () => {
    try {
      const res = await cameras.list();
      setCameraList(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async (id) => {
    try {
      const res = await cameras.test(id);
      alert(res.data.success ? `OK: ${res.data.message} (${res.data.latency_ms?.toFixed(0)}ms)` : `Error: ${res.data.message}`);
      loadCameras();
    } catch (err) {
      alert('Error al probar conexión');
    }
  };

  const handleSnapshot = async (cam) => {
    try {
      await cameras.downloadSnapshot(cam.id, cam.name);
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Error al capturar snapshot');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar cámara?')) return;
    await cameras.delete(id);
    loadCameras();
  };

  const statusColor = {
    online: 'text-green-400',
    offline: 'text-gray-400',
    error: 'text-red-400',
    degraded: 'text-yellow-400',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Cámaras</h1>
          <p className="text-gray-400">Administrar cámaras IP Dahua</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Agregar Cámara
        </button>
      </div>

      {showForm && (
        <CameraForm
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadCameras(); }}
        />
      )}

      {loading ? (
        <p className="text-gray-500">Cargando...</p>
      ) : cameraList.length === 0 ? (
        <div className="card text-center py-12">
          <CameraIcon className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No hay cámaras registradas</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameraList.map((cam) => (
            <div key={cam.id} className="card">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold">{cam.name}</h3>
                  <p className="text-sm text-gray-400">{cam.location || cam.ip_address}</p>
                </div>
                <span className={`text-sm capitalize ${statusColor[cam.status] || 'text-gray-400'}`}>
                  {cam.status}
                </span>
              </div>
              <div className="text-sm text-gray-400 space-y-1 mb-4">
                <p>Marca: {cam.brand} {cam.model && `· ${cam.model}`}</p>
                <p>Canal: {cam.channel} · IA: {cam.ai_enabled ? 'Activa' : 'Inactiva'}</p>
                <p>FPS análisis: {cam.ai_fps}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleTest(cam.id)} className="btn-secondary text-sm flex items-center gap-1">
                  <Wifi className="w-3 h-3" /> Probar
                </button>
                <button onClick={() => handleSnapshot(cam)} className="btn-secondary text-sm flex items-center gap-1">
                  <CameraIcon className="w-3 h-3" /> Snapshot
                </button>
                <button onClick={() => handleDelete(cam.id)} className="btn-secondary text-sm text-red-400">
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
