/** Extract display text from event + LLM metadata. */

function cleanText(value) {
  if (value == null) return null;
  const text = String(value).trim();
  if (!text || ['null', 'none', 'n/a', 'no visible'].includes(text.toLowerCase())) {
    return null;
  }
  return text;
}

export function getEventObservation(event) {
  const parsed = event?.metadata?.llm_analysis?.parsed;
  if (parsed) {
    const summary = cleanText(parsed.summary);
    if (summary) return summary;

    const parts = [
      cleanText(parsed.scene_description),
      cleanText(parsed.person_description),
    ].filter(Boolean);
    if (parts.length) return parts.join(' · ');
  }

  const raw = event?.metadata?.llm_analysis?.text;
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (trimmed && trimmed.length <= 600 && !trimmed.startsWith('{')) {
      return trimmed;
    }
  }

  return cleanText(event?.description);
}

export function getEventReview(event) {
  return getEventObservation(event) || event?.event_type || 'Alerta';
}

export function getEventClothing(event) {
  const parsed = event?.metadata?.llm_analysis?.parsed;
  const clothing = parsed?.person_clothing || parsed?.clothing;
  return cleanText(clothing);
}

export function getEventContextEval(event) {
  const parsed = event?.metadata?.llm_analysis?.parsed;
  return cleanText(parsed?.context_evaluation || parsed?.context_match);
}

export function isLlmPending(event) {
  if (event?.metadata?.llm_analysis) return false;
  return Boolean(event?.llm_pending);
}

export function needsObservation(event) {
  if (!event?.snapshot_url) return false;
  if (event?.metadata?.llm_analysis) return false;
  if (event?.llm_pending) return false;
  return true;
}

export function mergeEventUpdate(list, data) {
  const idx = list.findIndex((e) => e.id === data.id);
  if (idx >= 0) {
    const next = [...list];
    next[idx] = {
      ...next[idx],
      ...data,
      llm_pending: data.llm_updated ? false : (data.llm_pending ?? next[idx].llm_pending),
    };
    return next;
  }
  if (data.llm_updated) return list;
  return [data, ...list];
}
