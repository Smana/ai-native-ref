import { Element, type Ctx } from '../engine/scene.js';
import { Track, easing, clamp01 } from '../engine/tween.js';
import {
  arrowHead,
  font,
  pathLength,
  pointAt,
  rgba,
  roundRect,
  strokePolyline,
  subPath,
  type Pt,
} from '../engine/draw.js';
import { theme } from './theme.js';

export interface EdgeLabel {
  text: string;
  x: number;
  y: number;
  align?: CanvasTextAlign;
}

export interface EdgeOptions {
  points: Pt[];
  color?: string;
  label?: EdgeLabel;
  /** Arrowheads at both ends, flow in both directions. */
  both?: boolean;
  dashed?: boolean;
  width?: number;
}

interface Packet {
  at: number;
  dur: number;
  text?: string;
  color?: string;
}

/**
 * A connector. Tracks:
 *  - progress: 0..1, the line draws from its source to its target
 *  - flow: 0..1, intensity of the moving dots (an "active path")
 * Packets are one-shot labelled pills that travel along the edge.
 */
export class Edge extends Element {
  readonly progress = new Track(0);
  readonly flow = new Track(0);
  private packets: Packet[] = [];
  private readonly length: number;

  constructor(readonly o: EdgeOptions) {
    super(true);
    this.z = 5;
    this.length = pathLength(o.points);
  }

  get color() {
    return this.o.color ?? theme.cyan;
  }

  drawIn(at: number, dur = 0.5): this {
    this.progress.to(1, at, dur, easing.inOutCubic);
    return this;
  }

  flowOn(at: number, dur = 0.4): this {
    this.flow.to(1, at, dur);
    return this;
  }

  flowOff(at: number, dur = 0.4): this {
    this.flow.to(0, at, dur);
    return this;
  }

  packet(at: number, dur = 0.8, text?: string, color?: string): this {
    this.packets.push({ at, dur, text, color });
    return this;
  }

  draw(ctx: Ctx, t: number): void {
    const p = this.progress.value(t);
    if (p <= 0) return;
    const c = this.color;
    const pts = this.o.points;
    const drawn = subPath(pts, p);

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = rgba(c, 0.75);
    ctx.lineWidth = this.o.width ?? 3;
    if (this.o.dashed) ctx.setLineDash([10, 8]);
    strokePolyline(ctx, drawn);
    ctx.setLineDash([]);

    ctx.fillStyle = rgba(c, 0.95);
    const tip = pointAt(pts, p);
    arrowHead(ctx, tip.p, tip.angle, 16);
    if (this.o.both && p >= 0.999) {
      const start = pointAt(pts, 0);
      arrowHead(ctx, start.p, start.angle + Math.PI, 16);
    }

    // flowing dots
    const f = this.flow.value(t) * (p >= 0.999 ? 1 : 0);
    if (f > 0) {
      const spacing = 46;
      const speed = 150; // px/s
      const n = Math.max(1, Math.floor(this.length / spacing));
      const dirs = this.o.both ? [1, -1] : [1];
      for (const dir of dirs) {
        for (let i = 0; i < n; i++) {
          let k = ((t * speed) / this.length + i / n) % 1;
          if (dir < 0) k = 1 - k;
          const fade = Math.min(1, k * 6, (1 - k) * 6);
          const { p: q } = pointAt(pts, k);
          ctx.beginPath();
          ctx.arc(q[0], q[1], dir > 0 ? 5 : 4, 0, Math.PI * 2);
          ctx.fillStyle = rgba(dir > 0 ? c : theme.text, 0.9 * f * fade);
          ctx.fill();
        }
      }
    }

    // label
    if (this.o.label) {
      const la = clamp01((p - 0.5) / 0.5);
      if (la > 0) {
        const L = this.o.label;
        ctx.save();
        ctx.globalAlpha *= la;
        ctx.font = font(theme.fonts.mono, 26, 500);
        ctx.textAlign = L.align ?? 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = theme.muted;
        L.text.split('\n').forEach((line, i) => ctx.fillText(line, L.x, L.y + i * 31));
        ctx.restore();
      }
    }

    // packets
    for (const pk of this.packets) {
      const k = (t - pk.at) / pk.dur;
      if (k <= 0 || k >= 1) continue;
      const { p: q } = pointAt(pts, easing.inOutSine(k));
      const fade = Math.min(1, k * 5, (1 - k) * 5);
      const pc = pk.color ?? c;
      ctx.save();
      ctx.globalAlpha *= fade;
      if (pk.text) {
        ctx.font = font(theme.fonts.mono, 24, 700);
        const tw = ctx.measureText(pk.text).width + 24;
        ctx.shadowColor = rgba(pc, 0.7);
        ctx.shadowBlur = 18;
        roundRect(ctx, q[0] - tw / 2, q[1] - 19, tw, 38, 19);
        ctx.fillStyle = pc;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = theme.bg;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(pk.text, q[0], q[1] + 1);
      } else {
        ctx.shadowColor = pc;
        ctx.shadowBlur = 20;
        ctx.beginPath();
        ctx.arc(q[0], q[1], 9, 0, Math.PI * 2);
        ctx.fillStyle = pc;
        ctx.fill();
      }
      ctx.restore();
    }
  }
}
