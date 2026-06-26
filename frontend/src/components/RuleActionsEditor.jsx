const CHANNELS = [
  { id: 'telegram', label: 'Telegram', hint: 'Envía mensaje + captura (requiere bot en .env)' },
  { id: 'webhook', label: 'Webhook HTTP', hint: 'POST JSON a URL configurada' },
  { id: 'mqtt', label: 'MQTT', hint: 'Publica en broker configurado en .env' },
  { id: 'visual_alert', label: 'Panel web', hint: 'Aparece en Eventos y Dashboard en tiempo real' },
  { id: 'sound_alert', label: 'Alerta sonora', hint: 'Beep en navegador (Eventos abierto)' },
];

export function formatRuleChannels(actions = {}) {
  if (!actions) return '-';
  const labels = CHANNELS.filter((c) => actions[c.id]).map((c) => c.label);
  return labels.length ? labels.join(', ') : 'Solo panel';
}

export default function RuleActionsEditor({ actions, onChange }) {
  const toggle = (key) => {
    onChange({ ...actions, [key]: !actions[key] });
  };

  return (
    <div className="col-span-2 space-y-3 p-4 bg-dark-900 rounded-lg border border-dark-700">
      <div>
        <p className="text-sm font-medium text-primary-400">Acciones de alerta</p>
        <p className="text-xs text-gray-500 mt-1">
          Elegí por qué medios notificar cuando esta regla se dispare.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {CHANNELS.map(({ id, label, hint }) => (
          <label key={id} className="flex items-start gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              className="mt-1"
              checked={!!actions[id]}
              onChange={() => toggle(id)}
            />
            <span>
              <span className="block">{label}</span>
              <span className="block text-xs text-gray-500">{hint}</span>
            </span>
          </label>
        ))}
      </div>

      <div className="pt-2 border-t border-dark-700">
        <label className="flex items-start gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            className="mt-1"
            checked={actions.llm_describe !== false}
            onChange={(e) => onChange({ ...actions, llm_describe: e.target.checked })}
          />
          <span>
            <span className="block">Descripción IA de imagen</span>
            <span className="block text-xs text-gray-500">
              Primera alerta de la regla y luego cada 1 hora (requiere LLM activo)
            </span>
          </span>
        </label>
      </div>

      {actions.telegram && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-dark-700">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={actions.send_snapshot !== false}
              onChange={(e) => onChange({ ...actions, send_snapshot: e.target.checked })}
            />
            Adjuntar captura de la cámara en Telegram
          </label>
          <div>
            <label className="text-xs text-gray-400">Chat ID override (opcional)</label>
            <input
              className="input mt-1 text-sm"
              placeholder="Usa TELEGRAM_CHAT_ID del .env"
              value={actions.telegram_chat_id || ''}
              onChange={(e) => onChange({ ...actions, telegram_chat_id: e.target.value || undefined })}
            />
          </div>
        </div>
      )}

      {actions.webhook && (
        <div className="pt-2 border-t border-dark-700">
          <label className="text-xs text-gray-400">URL Webhook (opcional)</label>
          <input
            className="input mt-1 text-sm"
            placeholder="Usa WEBHOOK_DEFAULT_URL del .env"
            value={actions.webhook_url || ''}
            onChange={(e) => onChange({ ...actions, webhook_url: e.target.value || undefined })}
          />
        </div>
      )}
    </div>
  );
}
