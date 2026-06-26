import { useEffect, useState } from 'react';
import { Brain, Save, Zap, Camera } from 'lucide-react';
import { llm, cameras } from '../services/api';

export default function AIConfigPage() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [cameraList, setCameraList] = useState([]);
  const [testCameraId, setTestCameraId] = useState('');
  const [imageAnalysis, setImageAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    loadConfig();
    cameras.list().then((r) => {
      setCameraList(r.data);
      if (r.data.length) setTestCameraId(r.data[0].id);
    });
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const res = await llm.getConfig();
      setConfig(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setTestResult(null);
    try {
      const payload = { ...config };
      if (payload.openai_api_key === '') delete payload.openai_api_key;
      const res = await llm.updateConfig(payload);
      setConfig(res.data);
      alert('Configuración guardada');
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      await llm.updateConfig(config);
      const res = await llm.testConnection();
      setTestResult(res.data);
    } catch (err) {
      setTestResult({ success: false, message: err.response?.data?.detail || 'Error de conexión' });
    } finally {
      setTesting(false);
    }
  };

  const handleAnalyzeImage = async () => {
    if (!testCameraId) return;
    setAnalyzing(true);
    setImageAnalysis(null);
    try {
      const res = await llm.analyzeCameraImage(testCameraId);
      setImageAnalysis(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const apiError = err.response?.data?.error;
      const msg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join(', ')
          : apiError || err.message || 'Error al analizar imagen';
      setImageAnalysis({ success: false, error: msg });
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading || !config) {
    return <p className="text-gray-500">Cargando configuración IA...</p>;
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Brain className="w-7 h-7 text-primary-400" />
          IA — Análisis de Imágenes
        </h1>
        <p className="text-gray-400">
          Ollama local (sin API key) o OpenAI/ChatGPT para analizar snapshots de eventos
        </p>
      </div>

      <form onSubmit={handleSave} className="card space-y-5">
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(e) => setConfig((c) => ({ ...c, enabled: e.target.checked }))}
          />
          <span>Habilitar análisis LLM de imágenes</span>
        </label>

        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={config.analyze_on_event}
            onChange={(e) => setConfig((c) => ({ ...c, analyze_on_event: e.target.checked }))}
          />
          <span>Analizar automáticamente cada evento con snapshot</span>
        </label>

        <div>
          <label className="text-sm text-gray-400">Proveedor</label>
          <select
            className="input mt-1"
            value={config.provider}
            onChange={(e) => setConfig((c) => ({ ...c, provider: e.target.value }))}
          >
            <option value="ollama">Ollama (local)</option>
            <option value="openai">OpenAI / ChatGPT</option>
          </select>
        </div>

        {config.provider === 'ollama' && (
          <div className="grid grid-cols-2 gap-4 p-4 bg-dark-900 rounded-lg border border-dark-700">
            <div className="col-span-2 text-sm text-primary-400 font-medium">Configuración Ollama</div>
            <div className="col-span-2">
              <label className="text-sm text-gray-400">URL base</label>
              <input
                className="input mt-1"
                value={config.ollama_base_url || ''}
                onChange={(e) => setConfig((c) => ({ ...c, ollama_base_url: e.target.value }))}
                placeholder="http://host.docker.internal:11434"
              />
              <p className="text-xs text-gray-500 mt-1">
                Docker: use host.docker.internal. Linux: IP del host o http://172.17.0.1:11434
              </p>
            </div>
            <div>
              <label className="text-sm text-gray-400">Modelo visión</label>
              <input
                className="input mt-1"
                value={config.ollama_model || ''}
                onChange={(e) => setConfig((c) => ({ ...c, ollama_model: e.target.value }))}
                placeholder="llava, llama3.2-vision, moondream"
              />
              <p className="text-xs text-gray-500 mt-1">Ej: ollama pull llava</p>
            </div>
          </div>
        )}

        {config.provider === 'openai' && (
          <div className="grid grid-cols-2 gap-4 p-4 bg-dark-900 rounded-lg border border-dark-700">
            <div className="col-span-2 text-sm text-primary-400 font-medium">Configuración OpenAI / ChatGPT</div>
            <div className="col-span-2">
              <label className="text-sm text-gray-400">API Key</label>
              <input
                type="password"
                className="input mt-1"
                placeholder={config.openai_api_key_masked || 'sk-...'}
                onChange={(e) => setConfig((c) => ({ ...c, openai_api_key: e.target.value }))}
              />
              {config.openai_api_key_set && (
                <p className="text-xs text-green-400 mt-1">Key configurada: {config.openai_api_key_masked}</p>
              )}
            </div>
            <div>
              <label className="text-sm text-gray-400">Modelo</label>
              <input
                className="input mt-1"
                value={config.openai_model || ''}
                onChange={(e) => setConfig((c) => ({ ...c, openai_model: e.target.value }))}
                placeholder="gpt-4o-mini"
              />
            </div>
            <div>
              <label className="text-sm text-gray-400">Base URL (opcional)</label>
              <input
                className="input mt-1"
                value={config.openai_base_url || ''}
                onChange={(e) => setConfig((c) => ({ ...c, openai_base_url: e.target.value }))}
                placeholder="https://api.openai.com/v1"
              />
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-3 pt-2">
          <button type="submit" className="btn-primary flex items-center gap-2" disabled={saving}>
            <Save className="w-4 h-4" />
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
          <button type="button" onClick={handleTest} className="btn-secondary flex items-center gap-2" disabled={testing}>
            <Zap className="w-4 h-4" />
            {testing ? 'Probando...' : 'Probar conexión'}
          </button>
        </div>

        {testResult && (
          <div className={`text-sm p-3 rounded-lg ${testResult.success ? (testResult.model_available === false ? 'bg-yellow-900/30 text-yellow-200' : 'bg-green-900/30 text-green-300') : 'bg-red-900/30 text-red-300'}`}>
            {testResult.message}
            {testResult.model_available === false && (
              <p className="mt-2 text-xs">Instale un modelo de visión: <code>ollama pull llava</code> o <code>ollama pull moondream</code></p>
            )}
          </div>
        )}
      </form>

      <div className="card space-y-4">
        <h2 className="font-semibold flex items-center gap-2">
          <Camera className="w-5 h-5" /> Probar análisis de imagen
        </h2>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="text-sm text-gray-400">Cámara</label>
            <select className="input mt-1" value={testCameraId} onChange={(e) => setTestCameraId(e.target.value)}>
              {cameraList.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <button onClick={handleAnalyzeImage} className="btn-primary" disabled={analyzing}>
            {analyzing ? 'Analizando...' : 'Analizar ahora'}
          </button>
        </div>
        {imageAnalysis && (
          <div className="bg-dark-900 rounded-lg p-4 text-sm space-y-2">
            {imageAnalysis.success ? (
              <>
                <p className="text-green-400">Proveedor: {imageAnalysis.provider}</p>
                {imageAnalysis.parsed ? (
                  <pre className="text-gray-300 whitespace-pre-wrap overflow-auto max-h-64">
                    {JSON.stringify(imageAnalysis.parsed, null, 2)}
                  </pre>
                ) : (
                  <p className="text-gray-300 whitespace-pre-wrap">{imageAnalysis.analysis}</p>
                )}
              </>
            ) : (
              <p className="text-red-400">{imageAnalysis.error}</p>
            )}
          </div>
        )}
      </div>

      <div className="card text-sm text-gray-400 space-y-2">
        <p className="font-medium text-gray-300">También configurable en .env (Coolify):</p>
        <code className="block bg-dark-900 p-3 rounded text-xs">
          LLM_ENABLED=true<br />
          LLM_PROVIDER=ollama<br />
          OLLAMA_BASE_URL=http://host.docker.internal:11434<br />
          OLLAMA_MODEL=llava<br />
          OPENAI_API_KEY=sk-...<br />
          OPENAI_MODEL=gpt-4o-mini
        </code>
      </div>
    </div>
  );
}
