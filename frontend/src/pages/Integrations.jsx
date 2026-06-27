import { useEffect, useState } from 'react';
import { Plus, Save, Send } from 'lucide-react';
import { integrations, notifications } from '../services/api';

export default function IntegrationsPage() {
  const [list, setList] = useState([]);
  const [notifConfig, setNotifConfig] = useState(null);
  const [telegram, setTelegram] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [savingTelegram, setSavingTelegram] = useState(false);
  const [testingTelegram, setTestingTelegram] = useState(false);
  const [telegramTestResult, setTelegramTestResult] = useState(null);
  const [form, setForm] = useState({
    name: '',
    integration_type: 'webhook',
    config: { url: '' },
  });

  useEffect(() => {
    loadIntegrations();
    loadNotificationConfig();
  }, []);

  const loadNotificationConfig = async () => {
    try {
      const [cfgRes, tgRes] = await Promise.all([
        notifications.getConfig(),
        notifications.getTelegramConfig(),
      ]);
      setNotifConfig(cfgRes.data);
      setTelegram(tgRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  const loadIntegrations = async () => {
    const res = await integrations.list();
    setList(res.data.filter((item) => item.integration_type !== 'telegram'));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    await integrations.create(form);
    setShowForm(false);
    setForm({ name: '', integration_type: 'webhook', config: { url: '' } });
    loadIntegrations();
  };

  const handleSaveTelegram = async (e) => {
    e.preventDefault();
    setSavingTelegram(true);
    setTelegramTestResult(null);
    try {
      const payload = { ...telegram };
      if (payload.bot_token === '') delete payload.bot_token;
      delete payload.bot_token_set;
      delete payload.bot_token_masked;
      delete payload.configured;
      delete payload.source;
      const res = await notifications.updateTelegramConfig(payload);
      setTelegram(res.data);
      await loadNotificationConfig();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al guardar Telegram');
    } finally {
      setSavingTelegram(false);
    }
  };

  const handleTestTelegram = async () => {
    setTestingTelegram(true);
    setTelegramTestResult(null);
    try {
      if (telegram) {
        const payload = { ...telegram };
        if (payload.bot_token === '') delete payload.bot_token;
        delete payload.bot_token_set;
        delete payload.bot_token_masked;
        delete payload.configured;
        delete payload.source;
        await notifications.updateTelegramConfig(payload);
      }
      const res = await notifications.testTelegram();
      setTelegramTestResult({ success: true, message: res.data.message });
      await loadNotificationConfig();
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
  };

  if (!telegram) {
    return <p className="text-gray-500">Cargando integraciones...</p>;
  }

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

      <form onSubmit={handleSaveTelegram} className="card space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold text-lg">Telegram</h2>
            <p className="text-sm text-gray-400 mt-1">
              Bot para alertas con captura. Activá el envío en cada regla en{' '}
              <strong>Reglas → Acciones de alerta</strong>.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm shrink-0">
            <input
              type="checkbox"
              checked={telegram.enabled !== false}
              onChange={(e) => setTelegram((t) => ({ ...t, enabled: e.target.checked }))}
            />
            Habilitado
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-gray-400">Bot Token</label>
            <input
              className="input w-full mt-1 font-mono text-sm"
              type="password"
              placeholder={telegram.bot_token_set ? telegram.bot_token_masked : '123456789:ABCdef...'}
              value={telegram.bot_token ?? ''}
              onChange={(e) => setTelegram((t) => ({ ...t, bot_token: e.target.value }))}
              autoComplete="off"
            />
            {telegram.bot_token_set && !telegram.bot_token && (
              <p className="text-xs text-gray-500 mt-1">Token guardado ({telegram.bot_token_masked})</p>
            )}
          </div>
          <div>
            <label className="text-sm text-gray-400">Chat ID</label>
            <input
              className="input w-full mt-1 font-mono text-sm"
              placeholder="-1001234567890 o 987654321"
              value={telegram.chat_id || ''}
              onChange={(e) => setTelegram((t) => ({ ...t, chat_id: e.target.value }))}
            />
          </div>
        </div>

        <details className="text-xs text-gray-500">
          <summary className="cursor-pointer text-gray-400 hover:text-gray-300">¿Cómo obtener token y chat ID?</summary>
          <ol className="mt-2 list-decimal list-inside space-y-1 pl-1">
            <li>Hablá con @BotFather en Telegram → /newbot → copiá el token.</li>
            <li>Escribile un mensaje a tu bot.</li>
            <li>Abrí <code className="text-primary-400">https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code> y buscá <code>chat.id</code>.</li>
          </ol>
        </details>

        <div className="flex items-center gap-3 flex-wrap">
          <span className={`text-sm ${telegram.configured ? 'text-green-400' : 'text-yellow-400'}`}>
            {telegram.configured
              ? `Configurado${telegram.source === 'database' ? ' (guardado en app)' : ' (.env)'}`
              : 'Falta token o chat ID'}
          </span>
          <button type="submit" disabled={savingTelegram} className="btn-primary flex items-center gap-2 text-sm">
            <Save className="w-4 h-4" />
            {savingTelegram ? 'Guardando...' : 'Guardar'}
          </button>
          <button
            type="button"
            onClick={handleTestTelegram}
            disabled={testingTelegram || !telegram.configured}
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
      </form>

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
            Podés agregar webhooks o MQTT adicionales. Telegram se configura arriba.
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
