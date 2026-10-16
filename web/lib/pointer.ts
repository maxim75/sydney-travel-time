import type { MapRenderer } from "./renderer";

export interface PointerCallbacks {
  hover(i: number, x: number, y: number): void;  // hexagon under the pointer, or -1
  hideTip(): void;
  click(i: number): void;  // a hexagon was clicked or tapped
}
export interface PointerControl { unpin(): void; detach(): void; }

// Drag to pan, pinch or wheel to zoom, hover or tap to inspect. A tap on a touch screen pins
// the tooltip until the next gesture, since there is no hover to keep it open.
export function attachPointer(canvas: HTMLCanvasElement, map: MapRenderer, on: PointerCallbacks): PointerControl {
  const ptrs = new Map<number, [number, number]>();
  let moved = 0, lastPinch = 0, pinned = false;
  const local = (e: MouseEvent): [number, number] => {
    const r = canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };

  const down = (e: PointerEvent) => {
    canvas.setPointerCapture(e.pointerId);
    ptrs.set(e.pointerId, local(e)); moved = 0;
    if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; lastPinch = Math.hypot(a[0] - b[0], a[1] - b[1]); }
  };
  const move = (e: PointerEvent) => {
    const [x, y] = local(e);
    const last = ptrs.get(e.pointerId);
    if (!last) {
      if (e.pointerType === "mouse" && !pinned) on.hover(map.cellAtScreen(x, y), x, y);
      return;
    }
    ptrs.set(e.pointerId, [x, y]);
    if (ptrs.size === 1) {
      map.pan(x - last[0], y - last[1]);
      moved += Math.abs(x - last[0]) + Math.abs(y - last[1]);
      if (moved > 4) { canvas.classList.add("dragging"); on.hideTip(); pinned = false; }
    } else if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (lastPinch) map.zoomAt(d / lastPinch, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      lastPinch = d; moved = 99;
    }
  };
  const release = (e: PointerEvent) => {
    const wasTap = ptrs.size === 1 && moved <= 4;
    ptrs.delete(e.pointerId); canvas.classList.remove("dragging");
    if (ptrs.size < 2) lastPinch = 0;
    if (wasTap && e.type === "pointerup") {
      const [x, y] = local(e);
      const i = map.cellAtScreen(x, y);
      pinned = e.pointerType !== "mouse" && i >= 0;
      on.hover(i, x, y);
      if (i >= 0) on.click(i);
    }
  };
  const leave = (e: PointerEvent) => { if (e.pointerType === "mouse" && !pinned) on.hover(-1, 0, 0); };
  const wheel = (e: WheelEvent) => {
    e.preventDefault();
    const [x, y] = local(e);
    map.zoomAt(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0018)), x, y);
    on.hideTip(); pinned = false;
  };

  canvas.addEventListener("pointerdown", down);
  canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  canvas.addEventListener("pointerleave", leave);
  canvas.addEventListener("wheel", wheel, { passive: false });
  return {
    unpin: () => { pinned = false; },
    detach: () => {
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", release);
      canvas.removeEventListener("pointercancel", release);
      canvas.removeEventListener("pointerleave", leave);
      canvas.removeEventListener("wheel", wheel);
    },
  };
}
