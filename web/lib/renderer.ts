import { COS, type Geometry } from "./geometry";
import { CLASS_COUNT } from "./metrics";
import type { Building, Label, Transit } from "./types";

interface Tokens {
  surface: string; ink: string; ink2: string; ghost: string; nojourney: string; morning: string; toofar: string;
  ramp: string[]; hatch: CanvasPattern | string; sans: string; cond: string;
}

// Draws the hexagon map: pan and zoom state, the hexagon layer, rail and ferry lines, and labels.
// Colours and fonts come from the page's CSS tokens, re-read when the colour scheme changes.
export class MapRenderer {
  width = 0;
  height = 0;
  private canvas: HTMLCanvasElement;
  private g: Geometry;
  private labels: Label[];
  private transit: Transit | null;
  private ctx: CanvasRenderingContext2D;
  private dpr = 1;
  private k = 1;  // pixels per world unit
  private tx = 0;
  private ty = 0;
  private kFit = 1;  // k when the whole map fits
  private hover = -1;
  private cls: Uint8Array;
  private showLines = true;
  private building: Building | null = null;
  private linePaths: Record<string, Path2D> = {};
  private T!: Tokens;
  private frame = 0;
  private destroyed = false;
  // Hexagons are drawn into an offscreen layer (with a margin around the view) only when the
  // view settles or the colours change. While panning, zooming or hovering, the last layer is
  // just moved and scaled, so frames cost one image copy instead of 32k polygons.
  private layer = document.createElement("canvas");
  private lctx: CanvasRenderingContext2D;
  private lk = 0;
  private ltx = 0;
  private lty = 0;
  private margin = 0;
  private dirty = true;
  private moving = false;
  private settle: ReturnType<typeof setTimeout> | undefined;
  private resizeObserver: ResizeObserver;
  private themeObserver: MutationObserver;
  private darkQuery = matchMedia("(prefers-color-scheme: dark)");
  private retheme = () => { this.readTokens(); this.invalidate(); };

  constructor(canvas: HTMLCanvasElement, geometry: Geometry, labels: Label[], transit: Transit | null) {
    this.canvas = canvas;
    this.g = geometry;
    this.labels = labels;
    this.transit = transit;
    this.ctx = canvas.getContext("2d")!;
    this.lctx = this.layer.getContext("2d")!;
    this.cls = new Uint8Array(geometry.n);
    // rail, light rail and ferry lines as world-space paths, built once
    if (transit) for (const [layer, lines] of Object.entries(transit.lines)) {
      const p = new Path2D();
      for (const l of lines) for (let j = 0; j < l.length; j += 2) {
        const x = l[j] * COS, y = -l[j + 1];
        if (j) p.lineTo(x, y); else p.moveTo(x, y);
      }
      this.linePaths[layer] = p;
    }
    this.readTokens();
    this.darkQuery.addEventListener("change", this.retheme);
    this.themeObserver = new MutationObserver(this.retheme);
    this.themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    document.fonts?.ready.then(() => this.schedule());
  }

  destroy() {
    this.destroyed = true;
    this.resizeObserver.disconnect();
    this.themeObserver.disconnect();
    this.darkQuery.removeEventListener("change", this.retheme);
    cancelAnimationFrame(this.frame);
    clearTimeout(this.settle);
  }

  setClasses(cls: Uint8Array) { this.cls = cls; this.invalidate(); }
  setShowLines(show: boolean) { this.showLines = show && !!this.transit; this.invalidate(); }
  setBuilding(building: Building | null) { this.building = building; this.schedule(); }
  setHover(i: number) { if (i !== this.hover) { this.hover = i; this.schedule(); } }
  cellAtScreen(sx: number, sy: number) { return this.g.cellAt((sx - this.tx) / this.k, (sy - this.ty) / this.k); }

  pan(dx: number, dy: number) { this.tx += dx; this.ty += dy; this.interact(); this.schedule(); }
  zoomAt(f: number, sx: number, sy: number) {
    const nk = Math.min(Math.max(this.k * f, this.kFit * 0.7), this.kFit * 80);
    this.tx = sx - ((sx - this.tx) * nk) / this.k;
    this.ty = sy - ((sy - this.ty) * nk) / this.k;
    this.k = nk;
    this.interact(); this.schedule();
  }
  zoomBy(f: number) { this.zoomAt(f, this.width / 2, this.height / 2); }
  fitAll() {
    const { minX, minY, maxX, maxY, R } = this.g;
    this.fit(minX - R, minY - R, maxX + R, maxY + R);
    this.kFit = this.k;
    this.schedule();
  }
  zoomToCells(cells: number[]) {
    const { cx, cy, R } = this.g;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const i of cells) { x0 = Math.min(x0, cx[i]); x1 = Math.max(x1, cx[i]); y0 = Math.min(y0, cy[i]); y1 = Math.max(y1, cy[i]); }
    this.fit(x0 - R * 3, y0 - R * 3, x1 + R * 3, y1 + R * 3, 0.8);
    this.k = Math.min(this.k, this.kFit * 80);
    this.schedule();
  }

  private fit(x0: number, y0: number, x1: number, y1: number, pad = 0.92) {
    const { R } = this.g;
    const bw = Math.max(x1 - x0, R * 12), bh = Math.max(y1 - y0, R * 12);
    this.k = Math.min(this.width / bw, this.height / bh) * pad;
    this.tx = this.width / 2 - ((x0 + x1) / 2) * this.k;
    this.ty = this.height / 2 - ((y0 + y1) / 2) * this.k;
  }

  private resize() {
    const r = this.canvas.getBoundingClientRect();
    const first = this.width === 0, ox = this.width / 2, oy = this.height / 2;
    this.width = r.width; this.height = r.height; this.dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);
    if (first) this.fitAll();
    else { this.tx += this.width / 2 - ox; this.ty += this.height / 2 - oy; }
    this.invalidate();
  }

  private readTokens() {
    const cs = getComputedStyle(document.documentElement);
    const g = (name: string) => cs.getPropertyValue(name).trim();
    const T: Tokens = {
      surface: g("--surface"), ink: g("--ink"), ink2: g("--ink-2"), ghost: g("--ghost"), nojourney: g("--nojourney"),
      morning: g("--morning"), toofar: g("--toofar"), ramp: Array.from({ length: 10 }, (_, k) => g(`--r${k}`)),
      hatch: g("--nojourney"), sans: g("--sans"), cond: g("--cond"),
    };
    const c = document.createElement("canvas");
    c.width = c.height = 6;
    const x = c.getContext("2d")!;
    x.fillStyle = T.ghost; x.fillRect(0, 0, 6, 6);
    x.strokeStyle = T.nojourney; x.lineWidth = 1.6;
    x.beginPath(); x.moveTo(-1, 7); x.lineTo(7, -1); x.moveTo(-1, 1); x.lineTo(1, -1); x.moveTo(5, 7); x.lineTo(7, 5); x.stroke();
    T.hatch = this.ctx.createPattern(c, "repeat") ?? T.nojourney;
    this.T = T;
  }

  private schedule() {
    if (this.frame || this.destroyed) return;
    this.frame = requestAnimationFrame(() => { this.frame = 0; this.draw(); });
  }
  private invalidate() { this.dirty = true; this.schedule(); }
  private interact() {
    this.moving = true;
    clearTimeout(this.settle);
    this.settle = setTimeout(() => { this.moving = false; this.schedule(); }, 150);
  }

  private renderLayer() {
    const { n, cx, cy, start, P, R } = this.g, { k, dpr, lctx, T } = this;
    const MG = (this.margin = Math.round(Math.max(this.width, this.height) * 0.25));
    const LW = this.width + 2 * MG, LH = this.height + 2 * MG, ox = this.tx + MG, oy = this.ty + MG;
    if (this.layer.width !== Math.round(LW * dpr) || this.layer.height !== Math.round(LH * dpr)) {
      this.layer.width = Math.round(LW * dpr); this.layer.height = Math.round(LH * dpr);
    }
    lctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lctx.fillStyle = T.surface; lctx.fillRect(0, 0, LW, LH);
    const paths = Array.from({ length: CLASS_COUNT }, () => new Path2D());
    const m = R * k;
    for (let i = 0; i < n; i++) {
      const sx = cx[i] * k + ox, sy = cy[i] * k + oy;
      if (sx < -m || sy < -m || sx > LW + m || sy > LH + m) continue;
      const p = paths[this.cls[i]];
      for (let j = start[i]; j < start[i + 1]; j++) {
        const x = P[2 * j] * k + ox, y = P[2 * j + 1] * k + oy;
        if (j === start[i]) p.moveTo(x, y); else p.lineTo(x, y);
      }
      p.closePath();
    }
    const fills = [T.ghost, T.nojourney, T.hatch, ...T.ramp, T.morning, T.toofar];
    paths.forEach((p, c) => { lctx.fillStyle = fills[c]; lctx.fill(p); });
    if (m > 7) {  // surface gap between hexagons once they are big enough to see
      lctx.strokeStyle = T.surface; lctx.lineWidth = Math.min(2, m / 10);
      paths.forEach((p) => lctx.stroke(p));
    }
    if (this.showLines) this.drawLines(ox, oy);
    this.lk = k; this.ltx = this.tx; this.lty = this.ty; this.dirty = false;
  }

  private drawLines(ox: number, oy: number) {
    // paths are in world units, so draw them through the view transform and scale widths back to pixels
    const { lctx, k, dpr, T, linePaths } = this;
    lctx.save();
    lctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * ox, dpr * oy);
    lctx.lineJoin = lctx.lineCap = "round";
    const z = Math.min(1.5, Math.max(0.7, Math.sqrt(k / this.kFit) * 0.55));  // thinner when zoomed out
    const stroke = (p: Path2D | undefined, width: number, color: string, dash?: number[]) => {
      if (!p) return;
      lctx.lineWidth = (width * z) / k; lctx.strokeStyle = color;
      lctx.setLineDash(dash ? dash.map((d) => (d * z) / k) : []); lctx.stroke(p);
    };
    stroke(linePaths.ferry, 1.3, T.ink2, [4, 3]);
    stroke(linePaths.light_rail, 3.2, T.surface); stroke(linePaths.light_rail, 1.2, T.ink);
    stroke(linePaths.rail, 4, T.surface); stroke(linePaths.rail, 1.8, T.ink);
    lctx.restore();
  }

  private draw() {
    const { ctx, dpr, T } = this;
    if (!this.width || !this.height) return;  // not laid out yet
    if (this.dirty || (!this.moving && (this.lk !== this.k || this.ltx !== this.tx || this.lty !== this.ty))) this.renderLayer();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = T.surface; ctx.fillRect(0, 0, this.width, this.height);
    // layer point p (CSS px, minus margin) is world (p - ltx) / lk; on screen it is at s * p + tx - ltx * s
    const s = this.k / this.lk;
    ctx.setTransform(dpr * s, 0, 0, dpr * s, dpr * (this.tx - this.ltx * s), dpr * (this.ty - this.lty * s));
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(this.layer, -this.margin, -this.margin, this.layer.width / dpr, this.layer.height / dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const h = this.hover, { start, P } = this.g;
    if (h >= 0) {
      ctx.beginPath();
      for (let j = start[h]; j < start[h + 1]; j++) {
        const x = P[2 * j] * this.k + this.tx, y = P[2 * j + 1] * this.k + this.ty;
        if (j === start[h]) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.lineWidth = 2.5; ctx.strokeStyle = T.surface; ctx.stroke();
      ctx.lineWidth = 1.5; ctx.strokeStyle = T.ink; ctx.stroke();
    }
    this.drawLabels();
  }

  private drawLabels() {
    const { ctx, k, tx, ty, T, width: W, height: H } = this;
    const boxes: number[][] = [];
    const put = (text: string, x: number, y: number, font: string, color: string, weight = 2) => {
      ctx.font = font;
      const w = ctx.measureText(text).width;
      const b = [x - w / 2 - 3, y - 9, x + w / 2 + 3, y + 9];
      if (b[2] < 0 || b[0] > W || b[3] < 0 || b[1] > H) return;
      if (boxes.some((o) => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1])) return;
      boxes.push(b);
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineJoin = "round";
      ctx.lineWidth = weight * 2; ctx.strokeStyle = T.surface; ctx.strokeText(text, x, y);
      ctx.fillStyle = color; ctx.fillText(text, x, y);
    };
    const zoom = k / this.kFit, stations: [string, number, number][] = [];
    if (this.showLines && this.transit && zoom > 3) {
      for (const [name, lx, ly, layer] of this.transit.stations) {
        if (layer !== "rail" && zoom < 6) continue;
        const x = lx * COS * k + tx, y = -ly * k + ty;
        if (x < -10 || y < -10 || x > W + 10 || y > H + 10) continue;
        ctx.beginPath(); ctx.arc(x, y, layer === "rail" ? 3.5 : 2.6, 0, Math.PI * 2);
        ctx.fillStyle = T.surface; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = T.ink; ctx.stroke();
        stations.push([name.replace(/ (Station|Wharf|Light Rail)$/, ""), x, y]);
      }
    }
    // the dataset's building first, so labels avoid it
    if (this.building) {
      const qx = this.building.xy[0] * COS * k + tx, qy = -this.building.xy[1] * k + ty;
      ctx.beginPath(); ctx.arc(qx, qy, 6, 0, Math.PI * 2);
      ctx.fillStyle = T.ink; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = T.surface; ctx.stroke();
      boxes.push([qx - 8, qy - 8, qx + 8, qy + 8]);
      put(this.building.name, qx, qy - 17, `700 14px ${T.cond}`, T.ink, 3);
    }
    const showTier2 = zoom > 2.2;
    for (const [name, lx, ly, tier] of this.labels) {
      if (tier === 2 && !showTier2) continue;
      put(name, lx * COS * k + tx, -ly * k + ty, `${tier === 1 ? "600 13px" : "500 12px"} ${T.cond}`, T.ink, 2);
    }
    if (zoom > 9) for (const [name, x, y] of stations) put(name, x, y - 12, `500 11px ${T.sans}`, T.ink2, 2);
  }
}
