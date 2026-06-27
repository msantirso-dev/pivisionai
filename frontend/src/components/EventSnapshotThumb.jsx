import { useEffect, useState } from 'react';
import { Camera, X, ZoomIn } from 'lucide-react';
import { evidence } from '../services/api';
import EventReviewText from './EventReviewText';

export default function EventSnapshotThumb({
  snapshotUrl,
  alt = 'Evidencia del evento',
  size = 'md',
  event = null,
  showReviewInModal = true,
}) {
  const [thumbUrl, setThumbUrl] = useState(null);
  const [fullUrl, setFullUrl] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState(false);

  const sizeClass = size === 'sm' ? 'w-16 h-11' : size === 'lg' ? 'w-36 h-24' : 'w-28 h-20';

  useEffect(() => {
    if (!snapshotUrl) return undefined;

    let active = true;
    setError(false);

    evidence.loadSnapshotBlobUrl(snapshotUrl).then((url) => {
      if (!active) {
        URL.revokeObjectURL(url);
        return;
      }
      setThumbUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return url;
      });
      setFullUrl((prev) => {
        if (prev && prev !== url) URL.revokeObjectURL(prev);
        return url;
      });
    }).catch(() => {
      if (active) setError(true);
    });

    return () => {
      active = false;
    };
  }, [snapshotUrl]);

  useEffect(() => {
    return () => {
      if (thumbUrl) URL.revokeObjectURL(thumbUrl);
      if (fullUrl && fullUrl !== thumbUrl) URL.revokeObjectURL(fullUrl);
    };
  }, [thumbUrl, fullUrl]);

  useEffect(() => {
    if (!expanded) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setExpanded(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded]);

  if (!snapshotUrl) {
    return (
      <div className={`${sizeClass} rounded-md bg-dark-800 border border-dark-700 flex items-center justify-center text-gray-600`}>
        <Camera className="w-4 h-4" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`${sizeClass} rounded-md bg-dark-800 border border-dark-700 flex items-center justify-center text-gray-500 text-xs`}>
        Sin foto
      </div>
    );
  }

  if (!thumbUrl) {
    return <div className={`${sizeClass} rounded-md bg-dark-800 border border-dark-700 animate-pulse`} />;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className={`group relative ${sizeClass} rounded-md overflow-hidden border border-dark-600 hover:border-primary-500 transition-colors`}
        title="Ampliar captura"
      >
        <img src={thumbUrl} alt={alt} className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <ZoomIn className="w-4 h-4 text-white" />
        </div>
      </button>

      {expanded && (
        <div
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4"
          onClick={() => setExpanded(false)}
        >
          <button
            type="button"
            onClick={() => setExpanded(false)}
            className="absolute top-4 right-4 text-gray-300 hover:text-white"
            aria-label="Cerrar"
          >
            <X className="w-6 h-6" />
          </button>
          <div className="max-w-4xl w-full flex flex-col items-center gap-4" onClick={(e) => e.stopPropagation()}>
            <img
              src={fullUrl || thumbUrl}
              alt={alt}
              className="max-w-full max-h-[75vh] object-contain rounded-lg shadow-2xl border border-dark-600"
            />
            {showReviewInModal && event && (
              <div className="w-full card text-left">
                <EventReviewText event={event} showLabel />
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
