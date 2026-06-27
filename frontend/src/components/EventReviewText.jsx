import { useState } from 'react';
import { llm } from '../services/api';
import {
  getEventObservation,
  getEventClothing,
  getEventContextEval,
  isLlmPending,
  needsObservation,
} from '../utils/eventReview';

export default function EventReviewText({
  event,
  compact = false,
  showLabel = true,
  showAnalyzeButton = false,
  className = '',
}) {
  const [analyzing, setAnalyzing] = useState(false);
  const pending = isLlmPending(event) || analyzing;
  const observation = getEventObservation(event);
  const clothing = getEventClothing(event);
  const contextEval = getEventContextEval(event);
  const canAnalyze = showAnalyzeButton && needsObservation(event) && !analyzing;

  const handleAnalyze = async () => {
    if (!event?.id) return;
    setAnalyzing(true);
    try {
      await llm.analyzeEvent(event.id);
    } catch (err) {
      console.error(err);
    } finally {
      setAnalyzing(false);
    }
  };

  if (pending && !observation) {
    return (
      <div className={`space-y-1 ${className}`}>
        {showLabel && (
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Observación</p>
        )}
        <p className="text-xs text-primary-400 animate-pulse">Analizando imagen con IA…</p>
      </div>
    );
  }

  if (!observation && !clothing && !contextEval) {
    return (
      <div className={`space-y-1 ${className}`}>
        {showLabel && (
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Observación</p>
        )}
        <p className="text-xs text-gray-500 italic">Sin observación disponible</p>
        {canAnalyze && (
          <button
            type="button"
            onClick={handleAnalyze}
            className="text-xs text-primary-400 hover:text-primary-300 underline"
          >
            Generar con IA
          </button>
        )}
      </div>
    );
  }

  if (compact) {
    return (
      <div className={`space-y-0.5 ${className}`}>
        {showLabel && (
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Observación</p>
        )}
        <p className="text-sm text-gray-200 line-clamp-3" title={observation || undefined}>
          {observation}
        </p>
        {clothing && (
          <p className="text-xs text-amber-200/90 line-clamp-2" title={clothing}>
            Vestimenta: {clothing}
          </p>
        )}
        {canAnalyze && (
          <button
            type="button"
            onClick={handleAnalyze}
            className="text-xs text-primary-400 hover:text-primary-300 underline"
          >
            Regenerar observación
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={`space-y-1 max-w-md ${className}`}>
      {showLabel && (
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Observación</p>
      )}
      {observation && <p className="text-sm font-medium text-gray-100">{observation}</p>}
      {clothing && (
        <p className="text-xs text-amber-200/90">
          <span className="text-gray-500">Vestimenta:</span> {clothing}
        </p>
      )}
      {contextEval && (
        <p className="text-xs text-primary-300/90">
          <span className="text-gray-500">Contexto:</span> {contextEval}
        </p>
      )}
    </div>
  );
}
