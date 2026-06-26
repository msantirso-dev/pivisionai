import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { integrations } from '../services/api';

export default function IntegrationsPage() {
  const [list, setList] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: '',
    integration_type: 'webhook',
    config: { url: '' },
  });

  useEffect(() => {
    loadIntegrations();
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
          <p className="text-gray-400">Webhooks, MQTT y domótica</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Agregar
        </button>
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
                <option value="home_assistant">Home Assistant</option>
                <option value="fibaro">Fibaro HC3</option>
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
            Configure webhooks o MQTT en .env o agregue integraciones aquí.
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
