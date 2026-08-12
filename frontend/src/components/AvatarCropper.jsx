import React, { useState, useRef, useEffect } from 'react';
import { ZoomIn, Check, X } from 'lucide-react';

/*
 * Frame the pet yourself.
 *
 * A centre crop is a guess, and it is usually wrong: phone photos of a dog are
 * mostly floor, and the face — the one thing a profile picture is for — sits
 * off-centre. So the guardian positions it: drag to move, slider to zoom, and
 * what you see inside the circle is exactly what gets saved.
 *
 * The crop happens here, on a canvas, and only the cropped square is uploaded.
 * The server never has to guess, and a 12MP original never crosses the wire.
 */

const OUT_PX = 512;      // matches the server's stored size
const BOX = 260;         // on-screen diameter of the framing circle

export default function AvatarCropper({ file, onCancel, onCropped, busy }) {
  const [img, setImg] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef(null);
  const urlRef = useRef(null);

  useEffect(() => {
    if (!file) return undefined;
    const url = URL.createObjectURL(file);
    urlRef.current = url;
    const image = new Image();
    image.onload = () => {
      setImg(image);
      setZoom(1);
      setPos({ x: 0, y: 0 });
    };
    image.src = url;
    return () => { URL.revokeObjectURL(url); urlRef.current = null; };
  }, [file]);

  // Scale at which the photo exactly fills the circle — zoom multiplies this,
  // so zoom=1 is always "no gaps" regardless of the photo's shape.
  const baseScale = img ? Math.max(BOX / img.width, BOX / img.height) : 1;
  const scale = baseScale * zoom;

  const clamp = (next) => {
    if (!img) return next;
    const halfX = Math.max(0, (img.width * scale - BOX) / 2);
    const halfY = Math.max(0, (img.height * scale - BOX) / 2);
    return {
      x: Math.min(halfX, Math.max(-halfX, next.x)),
      y: Math.min(halfY, Math.max(-halfY, next.y)),
    };
  };

  useEffect(() => { setPos((p) => clamp(p)); }, [zoom, img]);

  const start = (e) => {
    const pt = e.touches ? e.touches[0] : e;
    drag.current = { x: pt.clientX - pos.x, y: pt.clientY - pos.y };
  };
  const move = (e) => {
    if (!drag.current) return;
    const pt = e.touches ? e.touches[0] : e;
    setPos(clamp({ x: pt.clientX - drag.current.x, y: pt.clientY - drag.current.y }));
  };
  const end = () => { drag.current = null; };

  const apply = () => {
    if (!img) return;
    const canvas = document.createElement('canvas');
    canvas.width = OUT_PX;
    canvas.height = OUT_PX;
    const ctx = canvas.getContext('2d');
    // Same transform as the preview, scaled from the 260px circle to 512px.
    const k = OUT_PX / BOX;
    const w = img.width * scale * k;
    const h = img.height * scale * k;
    ctx.drawImage(img, OUT_PX / 2 - w / 2 + pos.x * k, OUT_PX / 2 - h / 2 + pos.y * k, w, h);
    canvas.toBlob((blob) => {
      if (blob) onCropped(new File([blob], 'avatar.jpg', { type: 'image/jpeg' }));
    }, 'image/jpeg', 0.9);
  };

  return (
    <div className="glass-card rounded-2xl p-5 flex flex-col items-center gap-4">
      <p className="font-roboto text-white/80 text-sm text-center">
        Drag to move, slide to zoom. What's in the circle is what's saved.
      </p>

      <div
        className="relative rounded-full overflow-hidden bg-black/30 ring-2 ring-white/40 cursor-move touch-none select-none"
        style={{ width: BOX, height: BOX }}
        onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
        onTouchStart={start} onTouchMove={move} onTouchEnd={end}
      >
        {img && (
          <img
            src={urlRef.current}
            alt=""
            draggable={false}
            className="absolute pointer-events-none max-w-none"
            style={{
              width: img.width * scale,
              height: img.height * scale,
              left: '50%',
              top: '50%',
              transform: `translate(calc(-50% + ${pos.x}px), calc(-50% + ${pos.y}px))`,
            }}
          />
        )}
      </div>

      <div className="flex items-center gap-3 w-full max-w-xs">
        <ZoomIn className="w-4 h-4 text-white/60 flex-none" />
        <input
          type="range" min="1" max="4" step="0.01"
          value={zoom}
          onChange={(e) => setZoom(parseFloat(e.target.value))}
          className="flex-1 accent-white"
          aria-label="Zoom"
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={onCancel}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/15 hover:bg-white/25 text-white/85 font-roboto text-sm transition-colors"
        >
          <X className="w-4 h-4" /> Cancel
        </button>
        <button
          onClick={apply}
          disabled={!img || busy}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/35 hover:bg-white/45 disabled:opacity-50 text-white font-roboto font-bold text-sm transition-colors"
        >
          <Check className="w-4 h-4" /> {busy ? 'Saving…' : 'Use this photo'}
        </button>
      </div>
    </div>
  );
}
