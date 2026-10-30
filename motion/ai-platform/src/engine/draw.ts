import type { Ctx } from './scene.js';

export type Pt = [number, number];

export function roundRect(ctx: Ctx, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

/** Hex colour (#rrggbb) to rgba() with alpha. */
export function rgba(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

export function font(family: string, size: number, weight = 400): string {
  return `${weight} ${size}px ${family}`;
}

// ---- polylines -------------------------------------------------------------

export function pathLength(pts: Pt[]): number {
  let l = 0;
  for (let i = 1; i < pts.length; i++) l += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return l;
}

/** Point and direction (radians) at fraction `k` of the path. */
export function pointAt(pts: Pt[], k: number): { p: Pt; angle: number } {
  const total = pathLength(pts);
  let d = Math.min(Math.max(k, 0), 1) * total;
  for (let i = 1; i < pts.length; i++) {
    const [ax, ay] = pts[i - 1];
    const [bx, by] = pts[i];
    const seg = Math.hypot(bx - ax, by - ay);
    if (d <= seg || i === pts.length - 1) {
      const f = seg === 0 ? 0 : Math.min(d / seg, 1);
      return { p: [ax + (bx - ax) * f, ay + (by - ay) * f], angle: Math.atan2(by - ay, bx - ax) };
    }
    d -= seg;
  }
  return { p: pts[pts.length - 1], angle: 0 };
}

/** The sub-polyline from the start up to fraction `k`. */
export function subPath(pts: Pt[], k: number): Pt[] {
  const total = pathLength(pts);
  let d = Math.min(Math.max(k, 0), 1) * total;
  const out: Pt[] = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const [ax, ay] = pts[i - 1];
    const [bx, by] = pts[i];
    const seg = Math.hypot(bx - ax, by - ay);
    if (d >= seg) {
      out.push(pts[i]);
      d -= seg;
    } else {
      const f = seg === 0 ? 0 : d / seg;
      out.push([ax + (bx - ax) * f, ay + (by - ay) * f]);
      break;
    }
  }
  return out;
}

export function strokePolyline(ctx: Ctx, pts: Pt[]) {
  if (pts.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.stroke();
}

export function arrowHead(ctx: Ctx, p: Pt, angle: number, size: number) {
  ctx.save();
  ctx.translate(p[0], p[1]);
  ctx.rotate(angle);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(-size, -size * 0.55);
  ctx.lineTo(-size * 0.75, 0);
  ctx.lineTo(-size, size * 0.55);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

// ---- text --------------------------------------------------------------------

export interface Run {
  text: string;
  accent: boolean;
}

/** Parse "plain **accent** plain" into runs. */
export function parseAccents(s: string): Run[] {
  const runs: Run[] = [];
  s.split('**').forEach((part, i) => {
    if (part) runs.push({ text: part, accent: i % 2 === 1 });
  });
  return runs;
}

/** Greedy word wrap of accent runs into lines of runs. */
export function wrapRuns(ctx: Ctx, runs: Run[], maxWidth: number): Run[][] {
  const words: Run[] = [];
  for (const r of runs) {
    for (const w of r.text.split(/( +)/)) if (w) words.push({ text: w, accent: r.accent });
  }
  const lines: Run[][] = [];
  let line: Run[] = [];
  let width = 0;
  for (const w of words) {
    const ww = ctx.measureText(w.text).width;
    if (/^ +$/.test(w.text)) {
      if (line.length) {
        line.push(w);
        width += ww;
      }
      continue;
    }
    if (width + ww > maxWidth && line.length) {
      while (line.length && /^ +$/.test(line[line.length - 1].text)) line.pop();
      lines.push(line);
      line = [];
      width = 0;
    }
    line.push(w);
    width += ww;
  }
  if (line.length) lines.push(line);
  return lines;
}

export function runsWidth(ctx: Ctx, line: Run[]): number {
  return line.reduce((s, r) => s + ctx.measureText(r.text).width, 0);
}
