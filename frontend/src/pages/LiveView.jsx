import { useEffect, useState, useRef, useMemo } from 'react';
import { Grid2X2, Grid3X3, Square, LayoutGrid, RefreshCw } from 'lucide-react';
import { cameras } from '../services/api';
import clsx from 'clsx';

const GRID_OPTIONS = [
  { size: 1, icon: Square, label: '1' },
  { size: 4, icon: Grid2X2, label: '4' },
  { size: 9, icon: Grid3X3, label: '9' },
  { size: 16, icon: LayoutGrid, label: '16' },
];

async function parseApiError(err) {
  if (err.response?.data instanceof Blob) {
    try {
      const text = await err.response.data.text();
      const json = JSON.parse(text);
      return json.detail || text;
    } catch {
      return 'Error al obtener imagen';
    }
  }
  return err.response?.data?.detail || err.message || 'Sin conexión';
}

export default function LiveViewPage() {
  const [cameraList, setCameraList] = useState([]);
  const [gridSize, setGridSize] = useState(4);
  const [snapshots, setSnapshots] = useState({});
  const [errors, setErrors] = useState({});
  const [sources, setSources] = useState({});
  const [initialLoading, setInitialLoading] = useState({});
  const [pageLoading, setPageLoading] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(10);
  const blobUrls = useRef({});
  const refreshLock = useRef(false);
  const hasImageRef = useRef({});

  const visibleCameras = useMemo(
    () => cameraList.slice(0, gridSize),
    [cameraList, gridSize]
  );

  useEffect(() => {
    cameras.list().then((res) => {
      setCameraList(res.data);
      setPageLoading(false);
    });
  }, []);

  useEffect(() => {
    return () => {
      Object.values(blobUrls.current).forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  const refreshOne = async (cam, showSpinner = false) => {
    const hasImage = !!hasImageRef.current[cam.id];
    if (showSpinner && !hasImage) {
      setInitialLoading((prev) => ({ ...prev, [cam.id]: true }));
    }
    try {
      const blob = await cameras.liveSnapshot(cam.id);
      const objectUrl = URL.createObjectURL(blob);
      if (blobUrls.current[cam.id]) {
        URL.revokeObjectURL(blobUrls.current[cam.id]);
      }
      blobUrls.current[cam.id] = objectUrl;
      hasImageRef.current[cam.id] = true;
      setSnapshots((prev) => ({ ...prev, [cam.id]: objectUrl }));
      setErrors((prev) => ({ ...prev, [cam.id]: null }));
      setSources((prev) => ({
        ...prev,
        [cam.id]: cam.connection_mode === 'cloud'
          ? 'Dahua Cloud'
          : cam.brand === 'dahua'
            ? 'Dahua API'
            : 'RTSP',
      }));
    } catch (err) {
      const msg = await parseApiError(err);
      if (!hasImage) {
        setSnapshots((prev) => ({ ...prev, [cam.id]: null }));
      }
      setErrors((prev) => ({ ...prev, [cam.id]: msg }));
    } finally {
      setInitialLoading((prev) => ({ ...prev, [cam.id]: false }));
    }
  };

  const refreshSnapshots = async (showSpinner = false) => {
    if (refreshLock.current || visibleCameras.length === 0) return;
    refreshLock.current = true;
    try {
      for (const cam of visibleCameras) {
        await refreshOne(cam, showSpinner);
      }
    } finally {
      refreshLock.current = false;
    }
  };

  useEffect(() => {
    if (visibleCameras.length === 0) return;

    refreshSnapshots(true);

    const timer = setInterval(() => refreshSnapshots(false), refreshInterval * 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleCameras, refreshInterval]);

  const gridClass = {
    1: 'grid-cols-1',
    4: 'grid-cols-2',
    9: 'grid-cols-3',
    16: 'grid-cols-4',
  }[gridSize] || 'grid-cols-2';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">Cámaras en Vivo</h1>
          <p className="text-gray-400">Dahua: API HTTP snapshot · actualización cada {refreshInterval}s</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refreshSnapshots(true)}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <RefreshCw className="w-4 h-4" /> Actualizar
          </button>
          <select
            className="input w-auto text-sm"
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
          >
            <option value={5}>5s refresh</option>
            <option value={10}>10s refresh</option>
            <option value={15}>15s refresh</option>
            <option value={30}>30s refresh</option>
          </select>
          <div className="flex bg-dark-800 rounded-lg border border-dark-700">
            {GRID_OPTIONS.map(({ size, icon: Icon, label }) => (
              <button
                key={size}
                onClick={() => setGridSize(size)}
                className={clsx(
                  'px-3 py-2 flex items-center gap-1 text-sm transition-colors',
                  gridSize === size ? 'bg-primary-600 text-white' : 'text-gray-400 hover:text-white'
                )}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {pageLoading ? (
        <p className="text-gray-500">Cargando cámaras...</p>
      ) : cameraList.length === 0 ? (
        <div className="card text-center py-12 text-gray-500">No hay cámaras registradas</div>
      ) : (
        <div className={clsx('grid gap-2', gridClass)}>
          {visibleCameras.map((cam) => {
            const imageUrl = snapshots[cam.id];
            const isLoading = initialLoading[cam.id] && !imageUrl;
            const isOnline = !!imageUrl;

            return (
              <div
                key={cam.id}
                className="relative bg-black rounded-lg overflow-hidden aspect-video border border-dark-700"
              >
                {imageUrl ? (
                  <img src={imageUrl} alt={cam.name} className="w-full h-full object-contain" />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-gray-500 p-4 text-center">
                    {isLoading ? (
                      <>
                        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary-500 mb-2" />
                        <span className="text-sm">
                          {cam.brand === 'dahua'
                            ? 'Obteniendo imagen (Dahua API)...'
                            : 'Conectando RTSP...'}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="text-red-400 text-sm font-medium mb-1">Sin señal</span>
                        <span className="text-xs text-gray-500">
                          {errors[cam.id] || 'Use Probar en Cámaras'}
                        </span>
                      </>
                    )}
                  </div>
                )}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                  <p className="text-sm font-medium truncate">{cam.name}</p>
                  <p className="text-xs text-gray-400 flex items-center gap-2">
                    <span className={isOnline ? 'text-green-400' : isLoading ? 'text-yellow-400' : 'text-red-400'}>
                      {isOnline ? 'online' : isLoading ? 'conectando' : 'offline'}
                    </span>
                    {sources[cam.id] && `· ${sources[cam.id]}`}
                    {cam.ip_address && ` · ${cam.ip_address}`}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
