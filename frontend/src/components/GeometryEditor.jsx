import { useRef, useEffect, useState, useCallback } from 'react';
import { Trash2, Save } from 'lucide-react';

export default function GeometryEditor({ imageUrl, ruleType, geometry, onChange, width = 640, height = 360 }) {
  const canvasRef = useRef(null);
  const [points, setPoints] = useState([]);
  const [lineStart, setLineStart] = useState(null);
  const imgRef = useRef(null);

  useEffect(() => {
    if (geometry?.line) {
      setLineStart(geometry.line.start);
      setPoints([geometry.line.end]);
    } else if (geometry?.polygon) {
      setPoints(geometry.polygon);
      setLineStart(null);
    }
  }, [geometry]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    const img = imgRef.current;
    if (!canvas || !ctx || !img?.complete) return;

    canvas.width = width;
    canvas.height = height;
    ctx.drawImage(img, 0, 0, width, height);

    if (ruleType === 'line_crossing' && lineStart && points[0]) {
      ctx.strokeStyle = '#3b82f6';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(lineStart[0], lineStart[1]);
      ctx.lineTo(points[0][0], points[0][1]);
      ctx.stroke();
      ctx.fillStyle = '#3b82f6';
      ctx.beginPath();
      ctx.arc(lineStart[0], lineStart[1], 6, 0, Math.PI * 2);
      ctx.arc(points[0][0], points[0][1], 6, 0, Math.PI * 2);
      ctx.fill();
    }

    if (ruleType === 'zone_intrusion' && points.length >= 2) {
      ctx.strokeStyle = '#ef4444';
      ctx.fillStyle = 'rgba(239, 68, 68, 0.2)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      points.forEach((p) => ctx.lineTo(p[0], p[1]));
      if (points.length >= 3) ctx.closePath();
      ctx.stroke();
      if (points.length >= 3) ctx.fill();
      points.forEach((p) => {
        ctx.fillStyle = '#ef4444';
        ctx.beginPath();
        ctx.arc(p[0], p[1], 5, 0, Math.PI * 2);
        ctx.fill();
      });
    }
  }, [lineStart, points, ruleType, width, height]);

  useEffect(() => {
    draw();
  }, [draw, imageUrl]);

  const handleClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const scaleX = width / rect.width;
    const scaleY = height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    if (ruleType === 'line_crossing') {
      if (!lineStart) {
        setLineStart([x, y]);
      } else {
        const newPoints = [[x, y]];
        setPoints(newPoints);
        onChange({ line: { start: lineStart, end: [x, y] }, direction: 'any', reference_size: { width, height } });
      }
    } else {
      const newPoints = [...points, [x, y]];
      setPoints(newPoints);
      if (newPoints.length >= 3) {
        onChange({ polygon: newPoints, reference_size: { width, height } });
      }
    }
  };

  const handleClear = () => {
    setPoints([]);
    setLineStart(null);
    onChange(ruleType === 'line_crossing' ? {} : {});
    draw();
  };

  return (
    <div className="space-y-2">
      <img ref={imgRef} src={imageUrl} alt="Snapshot" className="hidden" crossOrigin="anonymous" onLoad={draw} />
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="w-full border border-dark-600 rounded-lg cursor-crosshair bg-black"
        onClick={handleClick}
      />
      <div className="flex gap-2 text-sm text-gray-400">
        {ruleType === 'line_crossing' ? (
          <span>Click: punto inicio → punto fin de la línea</span>
        ) : (
          <span>Click: agregar vértices del polígono (mín. 3)</span>
        )}
        <button onClick={handleClear} className="ml-auto btn-secondary text-xs flex items-center gap-1">
          <Trash2 className="w-3 h-3" /> Limpiar
        </button>
      </div>
    </div>
  );
}
