import { useEffect, useState } from 'react';
import { Plus, Pencil } from 'lucide-react';
import { rules, cameras } from '../services/api';
import SeverityBadge from '../components/SeverityBadge';
import GeometryEditor from '../components/GeometryEditor';
import RuleActionsEditor, { formatRuleChannels, formatRuleContext } from '../components/RuleActionsEditor';

const OBJECT_CLASS_OPTIONS = [
  { id: 'person', label: 'Persona' },
  { id: 'car', label: 'Auto' },
  { id: 'motorcycle', label: 'Moto' },
  { id: 'bicycle', label: 'Bicicleta' },
  { id: 'truck', label: 'Camión' },
  { id: 'bus', label: 'Bus' },
];

const DEFAULT_GEOMETRY_REF = { width: 640, height: 360 };

const DEFAULT_FORM = {
  camera_id: '',
  name: '',
  rule_type: 'zone_intrusion',
  severity: 'medium',
  object_classes: ['person'],
  geometry: {},
  context_description: '',
  actions: {
    telegram: false,
    webhook: false,
    mqtt: false,
    visual_alert: true,
    sound_alert: false,
    send_snapshot: true,
  },
};

export default function RulesPage() {
  const [ruleList, setRuleList] = useState([]);
  const [cameraList, setCameraList] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [snapshotUrl, setSnapshotUrl] = useState(null);
  const [fullFrame, setFullFrame] = useState(false);
  const [form, setForm] = useState({ ...DEFAULT_FORM });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [rulesRes, camsRes] = await Promise.all([rules.list(), cameras.list()]);
      setRuleList(rulesRes.data || []);
      setCameraList(camsRes.data || []);
      if (camsRes.data?.length > 0) {
        setForm((f) => (f.camera_id ? f : { ...f, camera_id: camsRes.data[0].id }));
      }
    } catch (err) {
      console.error('Error cargando reglas:', err);
    }
  };

  const loadSnapshot = async (cameraId) => {
    if (!cameraId) return;
    try {
      const url = await cameras.snapshotBlobUrl(cameraId);
      setSnapshotUrl((prev) => {
        if (prev?.startsWith('blob:')) URL.revokeObjectURL(prev);
        return url;
      });
    } catch {
      setSnapshotUrl(null);
    }
  };

  useEffect(() => {
    return () => {
      if (snapshotUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(snapshotUrl);
      }
    };
  }, [snapshotUrl]);

  const closeForm = () => {
    setShowForm(false);
    setEditingRule(null);
    setFullFrame(false);
    setSnapshotUrl((prev) => {
      if (prev?.startsWith('blob:')) URL.revokeObjectURL(prev);
      return null;
    });
  };

  const openEditor = async (rule) => {
    setShowForm(false);
    setEditingRule(rule);
    setForm({
      camera_id: rule.camera_id,
      name: rule.name,
      rule_type: rule.rule_type,
      severity: rule.severity,
      object_classes: Array.isArray(rule.object_classes) ? rule.object_classes : ['person'],
      geometry: rule.geometry || {},
      context_description: rule.context_description || '',
      actions: {
        ...DEFAULT_FORM.actions,
        ...(rule.actions || {}),
      },
    });
    await loadSnapshot(rule.camera_id);
  };

  const openCreateForm = async () => {
    const cameraId = form.camera_id || cameraList[0]?.id || '';
    setEditingRule(null);
    setShowForm(true);
    setFullFrame(false);
    setForm({
      ...DEFAULT_FORM,
      camera_id: cameraId,
    });
    if (cameraId) await loadSnapshot(cameraId);
  };

  const toggleObjectClass = (classId) => {
    setForm((f) => {
      const current = f.object_classes || [];
      const next = current.includes(classId)
        ? current.filter((c) => c !== classId)
        : [...current, classId];
      return { ...f, object_classes: next.length ? next : [classId] };
    });
  };

  const buildDefaultGeometry = (ruleType, useFullFrame = false) => {
    const ref = DEFAULT_GEOMETRY_REF;
    if (useFullFrame || ruleType === 'zone_intrusion') {
      return {
        polygon: [[10, 10], [630, 10], [630, 350], [10, 350]],
        reference_size: ref,
      };
    }
    return {
      line: { start: [100, 180], end: [540, 180] },
      direction: 'any',
      reference_size: ref,
    };
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.object_classes?.length) {
      alert('Seleccione al menos un tipo de objeto a detectar');
      return;
    }

    const geometry = form.geometry?.line || form.geometry?.polygon
      ? { ...form.geometry, reference_size: form.geometry.reference_size || DEFAULT_GEOMETRY_REF }
      : buildDefaultGeometry(form.rule_type, fullFrame);

    await rules.create({ ...form, geometry });
    closeForm();
    loadData();
  };

  const handleSaveRule = async () => {
    if (!editingRule) return;
    await rules.update(editingRule.id, {
      geometry: form.geometry,
      actions: form.actions,
      context_description: form.context_description || null,
    });
    closeForm();
    loadData();
  };

  const ruleTypeLabels = {
    line_crossing: 'Cruce de línea',
    zone_intrusion: 'Intrusión en zona',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Reglas Inteligentes</h1>
          <p className="text-gray-400">
            Las alertas se generan cuando YOLO detecta un objeto y cumple una regla activa.
          </p>
        </div>
        <button onClick={openCreateForm} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Nueva Regla
        </button>
      </div>

      {(showForm || editingRule) && (
        <div className="card">
          <h2 className="font-semibold mb-4">
            {editingRule ? `Editar regla: ${editingRule.name}` : 'Crear Regla'}
          </h2>

          {!editingRule ? (
            <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-400">Cámara</label>
                <select
                  className="input"
                  value={form.camera_id}
                  onChange={(e) => {
                    setForm((f) => ({ ...f, camera_id: e.target.value }));
                    loadSnapshot(e.target.value);
                  }}
                >
                  {cameraList.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm text-gray-400">Nombre</label>
                <input className="input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
              </div>
              <div>
                <label className="text-sm text-gray-400">Tipo de detección</label>
                <select className="input" value={form.rule_type} onChange={(e) => setForm((f) => ({ ...f, rule_type: e.target.value, geometry: {} }))}>
                  <option value="zone_intrusion">Intrusión en zona (recomendado)</option>
                  <option value="line_crossing">Cruce de línea</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-gray-400">Criticidad</label>
                <select className="input" value={form.severity} onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}>
                  <option value="low">Baja</option>
                  <option value="medium">Media</option>
                  <option value="high">Alta</option>
                  <option value="critical">Crítica</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-sm text-gray-400 mb-2 block">Objetos a detectar</label>
                <div className="flex flex-wrap gap-3">
                  {OBJECT_CLASS_OPTIONS.map(({ id, label }) => (
                    <label key={id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={(form.object_classes || []).includes(id)}
                        onChange={() => toggleObjectClass(id)}
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </div>
              {form.rule_type === 'zone_intrusion' && (
                <div className="col-span-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={fullFrame}
                      onChange={(e) => {
                        setFullFrame(e.target.checked);
                        if (e.target.checked) {
                          setForm((f) => ({ ...f, geometry: buildDefaultGeometry('zone_intrusion', true) }));
                        }
                      }}
                    />
                    Detectar en toda la imagen (sin dibujar zona)
                  </label>
                </div>
              )}
              {snapshotUrl && !fullFrame && (
                <div className="col-span-2">
                  <label className="text-sm text-gray-400 mb-2 block">Dibujar zona/línea</label>
                  <GeometryEditor
                    imageUrl={snapshotUrl}
                    ruleType={form.rule_type}
                    geometry={form.geometry}
                    onChange={(geo) => setForm((f) => ({ ...f, geometry: geo }))}
                  />
                </div>
              )}
              <RuleActionsEditor
                actions={form.actions}
                onChange={(actions) => setForm((f) => ({ ...f, actions }))}
                contextDescription={form.context_description}
                onContextChange={(value) => setForm((f) => ({ ...f, context_description: value }))}
              />
              <div className="col-span-2 flex gap-3">
                <button type="button" onClick={closeForm} className="btn-secondary">Cancelar</button>
                <button type="submit" className="btn-primary">Crear Regla</button>
              </div>
            </form>
          ) : (
            <div className="space-y-4">
              <RuleActionsEditor
                actions={form.actions}
                onChange={(actions) => setForm((f) => ({ ...f, actions }))}
                contextDescription={form.context_description}
                onContextChange={(value) => setForm((f) => ({ ...f, context_description: value }))}
              />
              {snapshotUrl ? (
                <GeometryEditor
                  imageUrl={snapshotUrl}
                  ruleType={form.rule_type}
                  geometry={form.geometry}
                  onChange={(geo) => setForm((f) => ({ ...f, geometry: geo }))}
                />
              ) : (
                <p className="text-gray-500">No se pudo cargar snapshot de la cámara</p>
              )}
              <div className="flex gap-3">
                <button onClick={closeForm} className="btn-secondary">Cancelar</button>
                <button onClick={handleSaveRule} className="btn-primary flex items-center gap-2">
                  <Pencil className="w-4 h-4" /> Guardar Regla
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b border-dark-700">
              <th className="pb-3 pr-4">Nombre</th>
              <th className="pb-3 pr-4">Tipo</th>
              <th className="pb-3 pr-4">Criticidad</th>
              <th className="pb-3 pr-4">Objetos</th>
              <th className="pb-3 pr-4">Contexto IA</th>
              <th className="pb-3 pr-4">Notificaciones</th>
              <th className="pb-3 pr-4">Estado</th>
              <th className="pb-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {ruleList.length === 0 ? (
              <tr><td colSpan={8} className="py-8 text-center text-gray-500">Sin reglas configuradas</td></tr>
            ) : (
              ruleList.map((rule) => (
                <tr key={rule.id} className="border-b border-dark-700/50">
                  <td className="py-3 pr-4 font-medium">{rule.name}</td>
                  <td className="py-3 pr-4">{ruleTypeLabels[rule.rule_type] || rule.rule_type}</td>
                  <td className="py-3 pr-4"><SeverityBadge severity={rule.severity} /></td>
                  <td className="py-3 pr-4">{rule.object_classes?.join(', ')}</td>
                  <td className="py-3 pr-4 text-xs text-gray-400 max-w-[200px]" title={rule.context_description || ''}>
                    {formatRuleContext(rule.context_description)}
                  </td>
                  <td className="py-3 pr-4 text-xs text-gray-400">{formatRuleChannels(rule.actions)}</td>
                  <td className="py-3 pr-4">{rule.is_active ? 'Activa' : 'Inactiva'}</td>
                  <td className="py-3">
                    <button onClick={() => openEditor(rule)} className="btn-secondary text-xs flex items-center gap-1">
                      <Pencil className="w-3 h-3" /> Editar
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
