import { useEffect, useState } from 'react';
import { Plus, Send } from 'lucide-react';
import { integrations, notifications } from '../services/api';

export default function IntegrationsPage() {
  const [list, setList] = useState([]);
  const [notifConfig, setNotifConfig] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [testingTelegram, setTestingTelegram] = useState(false);
  const [telegramTestResult, setTelegramTestResult] = useState(null);
  const [form, setForm] = useState({
    name: '',
    integration_type: 'webhook',
    config: { url: '' },
  });

  useEffect(() => {
    loadIntegrations();
    notifications.getConfig().then((r) => setNotifConfig(r.data)).catch(() => {});
  }, []);

  const loadIntegrations = async () => {
    const res = await integrations.list();
    setList(res.data);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    await integrations.create(form);
    setShowForm(false);
    setForm({ name: '', integration_type: 'webhook', config: { url: '' } });
    loadIntegrations();
  };

  const handleTestTelegram = async () => {
    setTestingTelegram(true);
    setTelegramTestResult(null);
    try {
      const res = await notifications.testTelegram();
      setTelegramTestResult({ success: true, message: res.data.message });
    } catch (err) {
      setTelegramTestResult({
        success: false,
        message: err.response?.data?.detail || 'Error al enviar prueba',
      });
    } finally {
      setTestingTelegram(false);
    }
  };

  const typeLabels = {
    webhook: 'Webhook',
    mqtt: 'MQTT',
    home_assistant: 'Home Assistant',
    fibaro: 'Fibaro HC3',
    telegram: 'Telegram',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Integraciones</h1>
          <p className="text-gray-400">Credenciales globales · activación por regla</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Agregar
        </button>
      </div>

      <div className="card space-y-4">
        <h2 className="font-semibold">Telegram</h2>
        <p className="text-sm text-gray-400">
          Configurá el bot en <code className="text-primary-400">.env</code> o Coolify. Activá el envío en cada regla en <strong>Reglas → Acciones de alerta</strong>.
        </p>
        <code className="block bg-dark-900 p-3 rounded text-xs text-gray-300">
          TELEGRAM_ENABLED=true<br />
          TELEGRAM_BOT_TOKEN=123456:ABC...<br />
          TELEGRAM_CHAT_ID=987654321
        </code>
        <p className="text-xs text-gray-500">
          1. Hablá con @BotFather → /newbot → copiá el token<br />
          2. Escribile a tu bot y abrí https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates para ver tu chat_id
        </p>
        <div className="flex items-center gap-3 flex-wrap">
          <span className={`text-sm ${notifConfig?.telegram_configured ? 'text-green-400' : 'text-yellow-400'}`}>
            {notifConfig?.telegram_configured ? 'Bot configurado' : 'Bot no configurado en .env'}
          </span>
          <button
            onClick={handleTestTelegram}
            disabled={testingTelegram || !notifConfig?.telegram_configured}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <Send className="w-4 h-4" />
            {testingTelegram ? 'Enviando...' : 'Probar Telegram'}
          </button>
        </div>
        {telegramTestResult && (
          <p className={`text-sm ${telegramTestResult.success ? 'text-green-400' : 'text-red-400'}`}>
            {telegramTestResult.message}
          </p>
        )}
      </div>

      <div className="card space-y-2">
        <h2 className="font-semibold">Canales disponibles por regla</h2>
        <ul className="text-sm text-gray-400 list-disc list-inside space-y-1">
          {(notifConfig?.channels || []).map((ch) => (
            <li key={ch.id}>
              <strong className="text-gray-300">{ch.label}</strong>
              {ch.supports_snapshot ? ' — incluye captura (Telegram)' : ''}
            </li>
          ))}
        </ul>
      </div>

      {showForm && (
        <div className="card">
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-400">Nombre</label>
              <input className="input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
            </div>
            <div>
              <label className="text-sm text-gray-400">Tipo</label>
              <select className="input" value={form.integration_type} onChange={(e) => setForm((f) => ({ ...f, integration_type: e.target.value }))}>
                <option value="webhook">Webhook</option>
                <option value="mqtt">MQTT</option>
                <option value="telegram">Telegram</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="text-sm text-gray-400">URL / Config</label>
              <input
                className="input"
                placeholder="https://hooks.example.com/events"
                value={form.config.url || ''}
                onChange={(e) => setForm((f) => ({ ...f, config: { ...f.config, url: e.target.value } }))}
              />
            </div>
            <div className="col-span-2 flex gap-3">
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
              <button type="submit" className="btn-primary">Guardar</button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {list.length === 0 ? (
          <div className="card col-span-2 text-center py-8 text-gray-500">
            Las credenciales van en .env. Las reglas definen qué canal usar en cada alerta.
          </div>
        ) : (
          list.map((item) => (
            <div key={item.id} className="card">
              <h3 className="font-semibold">{item.name}</h3>
              <p className="text-sm text-gray-400">{typeLabels[item.integration_type] || item.integration_type}</p>
              <p className="text-xs text-gray-500 mt-2 truncate">{JSON.stringify(item.config)}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
