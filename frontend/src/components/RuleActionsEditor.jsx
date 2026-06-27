const CHANNELS = [
  { id: 'telegram', label: 'Telegram', hint: 'Envía mensaje + captura (configurar en Integraciones)' },
  { id: 'webhook', label: 'Webhook HTTP', hint: 'POST JSON a URL configurada' },
  { id: 'mqtt', label: 'MQTT', hint: 'Publica en broker configurado en .env' },
  { id: 'visual_alert', label: 'Panel web', hint: 'Aparece en Eventos y Dashboard en tiempo real' },
  { id: 'sound_alert', label: 'Alerta sonora', hint: 'Beep en navegador (Eventos abierto)' },
];

export function formatRuleContext(context) {
  if (typeof context !== 'string' || !context.trim()) return '—';
  return context.length > 60 ? `${context.slice(0, 60)}…` : context;
}

export function formatRuleChannels(actions = {}) {
  if (!actions) return '-';
  const labels = CHANNELS.filter((c) => actions[c.id]).map((c) => c.label);
  return labels.length ? labels.join(', ') : 'Solo panel';
}

export default function RuleActionsEditor({ actions = {}, onChange, contextDescription = '', onContextChange }) {
  const safeActions = actions || {};
  const toggle = (key) => {
    onChange({ ...safeActions, [key]: !safeActions[key] });
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
              checked={!!safeActions[id]}
              onChange={() => toggle(id)}
            />
            <span>
              <span className="block">{label}</span>
              <span className="block text-xs text-gray-500">{hint}</span>
            </span>
          </label>
        ))}
      </div>

      <div className="pt-2 border-t border-dark-700 space-y-3">
        <p className="text-sm font-medium text-primary-400">Análisis de imagen con IA</p>
        <label className="flex items-start gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            className="mt-1"
            checked={safeActions.llm_describe !== false}
            onChange={(e) => onChange({ ...safeActions, llm_describe: e.target.checked })}
          />
          <span>
            <span className="block">Descripción IA de imagen</span>
            <span className="block text-xs text-gray-500">
              Genera una observación de lo que se ve en cada captura del evento (requiere IA activa)
            </span>
          </span>
        </label>
        {onContextChange && (
          <div>
            <label className="text-sm text-gray-400 mb-2 block">
              Qué debe identificar la IA en la imagen
            </label>
            <textarea
              className="input min-h-[96px] text-sm w-full"
              placeholder="Ej: Verificar si la persona lleva casco y chaleco en el área de carga. Ignorar vehículos estacionados."
              value={contextDescription}
              onChange={(e) => onContextChange(e.target.value)}
              disabled={safeActions.llm_describe === false}
            />
            <p className="text-xs text-gray-500 mt-1">
              {safeActions.llm_describe === false
                ? 'Activá "Descripción IA de imagen" para usar este contexto.'
                : 'El modelo de visión usará este texto para evaluar la captura cuando la regla dispare.'}
            </p>
          </div>
        )}
      </div>

      {safeActions.telegram && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-dark-700">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={safeActions.send_snapshot !== false}
              onChange={(e) => onChange({ ...safeActions, send_snapshot: e.target.checked })}
            />
            Adjuntar captura de la cámara en Telegram
          </label>
          <div>
            <label className="text-xs text-gray-400">Chat ID override (opcional)</label>
            <input
              className="input mt-1 text-sm"
              placeholder="Opcional: otro chat (usa el global si está vacío)"
              value={safeActions.telegram_chat_id || ''}
              onChange={(e) => onChange({ ...safeActions, telegram_chat_id: e.target.value || undefined })}
            />
          </div>
        </div>
      )}

      {safeActions.webhook && (
        <div className="pt-2 border-t border-dark-700">
          <label className="text-xs text-gray-400">URL Webhook (opcional)</label>
          <input
            className="input mt-1 text-sm"
            placeholder="Usa WEBHOOK_DEFAULT_URL del .env"
            value={safeActions.webhook_url || ''}
            onChange={(e) => onChange({ ...safeActions, webhook_url: e.target.value || undefined })}
          />
        </div>
      )}
    </div>
  );
}
