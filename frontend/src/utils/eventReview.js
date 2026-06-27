/** Extract display text from event + LLM metadata. */

export function getEventReview(event) {
  const parsed = event?.metadata?.llm_analysis?.parsed;
  if (parsed?.summary) return parsed.summary;
  return event?.description || event?.event_type || 'Alerta';
}

export function getEventClothing(event) {
  const parsed = event?.metadata?.llm_analysis?.parsed;
  const clothing = parsed?.person_clothing || parsed?.clothing;
  if (!clothing || ['null', 'none', 'n/a'].includes(String(clothing).trim().toLowerCase())) {
    return null;
  }
  return clothing;
}

export function getEventContextEval(event) {
  const parsed = event?.metadata?.llm_analysis?.parsed;
  return parsed?.context_evaluation || parsed?.context_match || null;
}

export function isLlmPending(event) {
  if (event?.metadata?.llm_analysis) return false;
  return Boolean(event?.llm_pending);
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
