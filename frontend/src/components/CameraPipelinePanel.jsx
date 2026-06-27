import { useEffect, useState } from 'react';
import { X, Gauge, Zap, ImageOff, RefreshCw } from 'lucide-react';
import { cameras } from '../services/api';

const STREAM_MODES = [
  { value: 'hybrid', label: 'Hybrid (recomendado)' },
  { value: 'sub', label: 'Sub stream (bajo costo)' },
  { value: 'main', label: 'Main stream (alta calidad)' },
  { value: 'auto', label: 'Auto' },
];

const LOCATION_TYPES = [
  { value: 'exterior', label: 'Exterior' },
  { value: 'interior', label: 'Interior' },
  { value: 'perimetro', label: 'Perímetro' },
  { value: 'acceso', label: 'Acceso' },
  { value: 'ptz', label: 'PTZ' },
];

export default function CameraPipelinePanel({ camera, onClose, onSaved }) {
  const [config, setConfig] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [abResult, setAbResult] = useState(null);
  const [recommendation, setRecommendation] = useState('hybrid');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [abRunning, setAbRunning] = useState(false);

  useEffect(() => {
    loadAll();
  }, [camera.id]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [cfgRes, metRes] = await Promise.all([
        cameras.pipeline.get(camera.id),
        cameras.pipeline.metrics(camera.id),
      ]);
      setConfig(cfgRes.data.config);
      setRecommendation(cfgRes.data.recommendation || 'hybrid');
      setMetrics(metRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const updateField = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await cameras.pipeline.update(camera.id, config);
      setRecommendation(res.data.recommendation);
      await loadAll();
      onSaved?.();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al guardar pipeline');
    } finally {
      setSaving(false);
    }
  };

  const handleAbTest = async () => {
    setAbRunning(true);
    try {
      const res = await cameras.pipeline.abTest(camera.id);
      setAbResult(res.data);
      setRecommendation(res.data.recommendation);
    } catch (err) {
      alert(err.response?.data?.detail || 'Error en prueba A/B');
    } finally {
      setAbRunning(false);
    }
  };

  const savings = metrics?.savings || {};
  const m = metrics?.metrics || {};

  const recLabel = {
    sub: 'Usar sub stream',
    main: 'Usar main stream',
    hybrid: 'Usar hybrid',
  };

  if (loading || !config) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
        <div className="card p-8">Cargando pipeline…</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="card w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold">Pipeline IA — {camera.name}</h2>
            <p className="text-sm text-gray-400">Análisis event-driven · ahorro de tokens y ancho de banda</p>
          </div>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <Gauge className="w-4 h-4 mx-auto mb-1 text-primary-400" />
            <p className="text-xs text-gray-400">FPS efectivo</p>
            <p className="font-semibold">{config.analysis_fps}</p>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <Zap className="w-4 h-4 mx-auto mb-1 text-yellow-400" />
            <p className="text-xs text-gray-400">LLM evitados</p>
            <p className="font-semibold">{m.llm_calls_avoided_total || 0}</p>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <ImageOff className="w-4 h-4 mx-auto mb-1 text-orange-400" />
            <p className="text-xs text-gray-400">Screenshots suprimidos</p>
            <p className="font-semibold">{m.screenshots_suppressed_total || 0}</p>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-400">Recomendación</p>
            <p className="font-semibold text-primary-300">{recLabel[recommendation] || recommendation}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <label className="block">
            <span className="text-sm text-gray-400">Modo de stream</span>
            <select
              className="input w-full mt-1"
              value={config.stream_mode || 'hybrid'}
              onChange={(e) => updateField('stream_mode', e.target.value)}
            >
              {STREAM_MODES.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">Tipo de ubicación</span>
            <select
              className="input w-full mt-1"
              value={config.location_type || 'exterior'}
              onChange={(e) => updateField('location_type', e.target.value)}
            >
              {LOCATION_TYPES.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">FPS análisis</span>
            <input
              type="number"
              step="0.5"
              min="0.5"
              max="30"
              className="input w-full mt-1"
              value={config.analysis_fps ?? 2}
              onChange={(e) => updateField('analysis_fps', parseFloat(e.target.value))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">FPS detector (YOLO)</span>
            <input
              type="number"
              step="0.5"
              min="0.25"
              max="15"
              className="input w-full mt-1"
              value={config.detector_fps ?? 1}
              onChange={(e) => updateField('detector_fps', parseFloat(e.target.value))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">Resolución análisis (px)</span>
            <input
              type="number"
              className="input w-full mt-1"
              value={config.analysis_resolution ?? 640}
              onChange={(e) => updateField('analysis_resolution', parseInt(e.target.value, 10))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">Cooldown (seg)</span>
            <input
              type="number"
              className="input w-full mt-1"
              value={config.cooldown_seconds ?? 30}
              onChange={(e) => updateField('cooldown_seconds', parseInt(e.target.value, 10))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">Área mínima movimiento</span>
            <input
              type="number"
              className="input w-full mt-1"
              value={config.min_motion_area ?? 500}
              onChange={(e) => updateField('min_motion_area', parseInt(e.target.value, 10))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">Umbral SSIM</span>
            <input
              type="number"
              step="0.01"
              min="0.5"
              max="1"
              className="input w-full mt-1"
              value={config.ssim_threshold ?? 0.92}
              onChange={(e) => updateField('ssim_threshold', parseFloat(e.target.value))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">Umbral pHash</span>
            <input
              type="number"
              className="input w-full mt-1"
              value={config.phash_threshold ?? 8}
              onChange={(e) => updateField('phash_threshold', parseInt(e.target.value, 10))}
            />
          </label>
          <label className="flex items-center gap-2 mt-6">
            <input
              type="checkbox"
              checked={config.llm_enabled !== false}
              onChange={(e) => updateField('llm_enabled', e.target.checked)}
            />
            <span className="text-sm">LLM habilitado en eventos</span>
          </label>
          <label className="flex items-center gap-2 mt-6">
            <input
              type="checkbox"
              checked={config.enable_ab_test === true}
              onChange={(e) => updateField('enable_ab_test', e.target.checked)}
            />
            <span className="text-sm">A/B test continuo main vs sub</span>
          </label>
        </div>

        <div className="flex flex-wrap gap-2 mb-6">
          <button type="button" onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? 'Guardando…' : 'Guardar configuración'}
          </button>
          <button type="button" onClick={handleAbTest} disabled={abRunning} className="btn-secondary flex items-center gap-1">
            <RefreshCw className={`w-4 h-4 ${abRunning ? 'animate-spin' : ''}`} />
            Probar main vs sub
          </button>
          <button type="button" onClick={loadAll} className="btn-secondary">Actualizar métricas</button>
        </div>

        {abResult && (
          <div className="mb-6 overflow-x-auto">
            <h3 className="font-semibold mb-2">Comparativa A/B</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="py-2">Métrica</th>
                  <th>Main</th>
                  <th>Sub</th>
                </tr>
              </thead>
              <tbody>
                <tr><td className="py-1">Detecciones avg</td><td>{abResult.comparison?.main_detections_avg?.toFixed(2)}</td><td>{abResult.comparison?.sub_detections_avg?.toFixed(2)}</td></tr>
                <tr><td className="py-1">Latencia avg (ms)</td><td>{abResult.comparison?.main_latency_ms_avg?.toFixed(0)}</td><td>{abResult.comparison?.sub_latency_ms_avg?.toFixed(0)}</td></tr>
                <tr><td className="py-1">Ancho de banda avg</td><td>{abResult.comparison?.main_bandwidth_avg?.toFixed(0)}</td><td>{abResult.comparison?.sub_bandwidth_avg?.toFixed(0)}</td></tr>
                <tr><td className="py-1">Ahorro estimado</td><td colSpan={2}>{abResult.comparison?.estimated_bandwidth_savings_pct}%</td></tr>
              </tbody>
            </table>
          </div>
        )}

        <details className="text-sm text-gray-400">
          <summary className="cursor-pointer font-medium text-gray-300">Métricas detalladas</summary>
          <pre className="mt-2 p-3 bg-gray-900 rounded text-xs overflow-x-auto">
            {JSON.stringify({ metrics: m, savings }, null, 2)}
          </pre>
        </details>
      </div>
    </div>
  );
}
