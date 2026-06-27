import { getEventReview, getEventClothing, getEventContextEval, isLlmPending } from '../utils/eventReview';

export default function EventReviewText({ event, compact = false }) {
  const pending = isLlmPending(event);
  const review = getEventReview(event);
  const clothing = getEventClothing(event);
  const contextEval = getEventContextEval(event);

  if (pending) {
    return (
      <div className="space-y-1">
        <p className="text-sm text-gray-300">{review}</p>
        <p className="text-xs text-primary-400 animate-pulse">Analizando imagen con IA…</p>
      </div>
    );
  }

  if (compact) {
    return (
      <p className="text-sm text-gray-200 line-clamp-2" title={review}>
        {review}
      </p>
    );
  }

  return (
    <div className="space-y-1 max-w-md">
      <p className="text-sm font-medium text-gray-100">{review}</p>
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
      <p className="text-xs text-gray-500">{event.event_type}</p>
    </div>
  );
}
