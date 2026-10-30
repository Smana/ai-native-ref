import { Element, type Ctx } from '../engine/scene.js';
import { Track, easing, lerp } from '../engine/tween.js';
import { roundRect, rgba, font, type Pt } from '../engine/draw.js';
import { theme } from './theme.js';
import { drawIcon, type IconName } from './Icon.js';

export interface NodeSegment {
  title: string;
  sub?: string;
  icon?: IconName;
}

export interface NodeOptions {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  sub?: string[];
  color?: string;
  icon?: IconName;
  /** Dashed inner box (e.g. a sandbox) with a corner label. */
  inner?: { label: string; lines: string[] };
  /** Horizontal segments instead of a title (e.g. "models | tools | token"). */
  segments?: NodeSegment[];
  dashed?: boolean;
  titleSize?: number;
  subSize?: number;
}

/**
 * A box on the diagram. Tracks:
 *  - opacity/dim (from Element)
 *  - pop: 0..1 entrance scale
 *  - glow: 0..1 highlight (active path)
 *  - inner: 0..1 reveal of the inner box
 *  - seg[i]: 0..1 reveal and seg glow per segment
 */
export class Node extends Element {
  readonly pop = new Track(0);
  readonly glow = new Track(0);
  readonly innerReveal = new Track(0);
  readonly segReveal: Track[];
  readonly segGlow: Track[];
  private pulses: number[] = [];

  constructor(readonly o: NodeOptions) {
    super(false);
    this.z = 10;
    this.segReveal = (o.segments ?? []).map(() => new Track(0));
    this.segGlow = (o.segments ?? []).map(() => new Track(0));
  }

  get color() {
    return this.o.color ?? theme.cyan;
  }

  // ---- anchors -------------------------------------------------------------
  get cx() {
    return this.o.x + this.o.w / 2;
  }
  get cy() {
    return this.o.y + this.o.h / 2;
  }
  top(dx = 0): Pt {
    return [this.cx + dx, this.o.y];
  }
  bottom(dx = 0): Pt {
    return [this.cx + dx, this.o.y + this.o.h];
  }
  left(dy = 0): Pt {
    return [this.o.x, this.cy + dy];
  }
  right(dy = 0): Pt {
    return [this.o.x + this.o.w, this.cy + dy];
  }
  /** Anchor at fractions of the box (0,0 = top-left). */
  at(fx: number, fy: number): Pt {
    return [this.o.x + this.o.w * fx, this.o.y + this.o.h * fy];
  }
  segAnchor(i: number, side: 'top' | 'bottom' = 'top'): Pt {
    const n = this.o.segments?.length ?? 1;
    const w = this.o.w / n;
    return [this.o.x + w * (i + 0.5), side === 'top' ? this.o.y : this.o.y + this.o.h];
  }

  // ---- choreography ----------------------------------------------------------
  override show(at: number, dur = 0.55): this {
    this.opacity.to(1, at, dur * 0.7, easing.outCubic);
    this.pop.to(1, at, dur, easing.outBack);
    return this;
  }

  highlight(at: number, dur = 0.4): this {
    this.glow.to(1, at, dur);
    return this;
  }

  unhighlight(at: number, dur = 0.4): this {
    this.glow.to(0, at, dur);
    return this;
  }

  /** An expanding ring at time `at`. */
  pulse(at: number): this {
    this.pulses.push(at);
    return this;
  }

  revealInner(at: number, dur = 0.5): this {
    this.innerReveal.to(1, at, dur, easing.outCubic);
    return this;
  }

  revealSegments(at: number, stagger = 0.25, dur = 0.4): this {
    this.segReveal.forEach((tr, i) => tr.to(1, at + i * stagger, dur, easing.outCubic));
    return this;
  }

  segHighlight(i: number, at: number, hold = 0.8): this {
    this.segGlow[i].to(1, at, 0.25).to(0, at + hold, 0.4);
    return this;
  }

  // ---- drawing ---------------------------------------------------------------
  draw(ctx: Ctx, t: number): void {
    const { x, y, w, h } = this.o;
    const c = this.color;
    const pop = this.pop.value(t);
    const glow = this.glow.value(t);
    const s = lerp(0.9, 1, pop);

    ctx.translate(this.cx, this.cy);
    ctx.scale(s, s);
    ctx.translate(-this.cx, -this.cy);

    // pulses
    for (const p of this.pulses) {
      const k = (t - p) / 0.9;
      if (k <= 0 || k >= 1) continue;
      ctx.save();
      ctx.strokeStyle = rgba(c, 0.6 * (1 - k));
      ctx.lineWidth = 3;
      const g = 26 * easing.outCubic(k);
      roundRect(ctx, x - g, y - g, w + 2 * g, h + 2 * g, 18 + g);
      ctx.stroke();
      ctx.restore();
    }

    // body
    ctx.save();
    if (glow > 0) {
      ctx.shadowColor = rgba(c, 0.55 * glow);
      ctx.shadowBlur = 36 * glow;
    }
    roundRect(ctx, x, y, w, h, 18);
    const grad = ctx.createLinearGradient(x, y, x, y + h);
    grad.addColorStop(0, lerpHex(theme.panel, theme.panelHi, glow));
    grad.addColorStop(1, theme.panel);
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.restore();

    ctx.save();
    if (this.o.dashed) ctx.setLineDash([12, 8]);
    ctx.strokeStyle = rgba(c, 0.5 + 0.5 * glow);
    ctx.lineWidth = 2.5 + 1.5 * glow;
    roundRect(ctx, x, y, w, h, 18);
    ctx.stroke();
    ctx.restore();

    if (this.o.segments) {
      this.drawSegments(ctx, t);
      return;
    }

    const titleSize = this.o.titleSize ?? 40;
    const subSize = this.o.subSize ?? 30;
    const sub = this.o.sub ?? [];
    const innerH = this.o.inner ? 100 : 0;
    const blockH = titleSize + sub.length * (subSize * 1.35) + (sub.length ? 8 : 0) + (innerH ? innerH + 16 : 0);
    let cy = y + (h - blockH) / 2 + titleSize * 0.82;

    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = theme.text;
    ctx.font = font(theme.fonts.mono, titleSize, 700);
    if (this.o.icon) {
      const iw = titleSize * 0.8;
      const tw = ctx.measureText(this.o.title).width;
      const left = this.cx - (tw + iw + 12) / 2;
      drawIcon(ctx, this.o.icon, left + iw / 2, cy - titleSize * 0.36, iw, c);
      ctx.textAlign = 'left';
      ctx.fillText(this.o.title, left + iw + 12, cy);
      ctx.textAlign = 'center';
    } else {
      ctx.fillText(this.o.title, this.cx, cy);
    }
    cy += 8;
    ctx.font = font(theme.fonts.mono, subSize, 400);
    ctx.fillStyle = theme.muted;
    for (const line of sub) {
      cy += subSize * 1.35;
      ctx.fillText(line, this.cx, cy);
    }

    if (this.o.inner) {
      const r = this.innerReveal.value(t);
      if (r > 0) {
        const ix = x + 26;
        const iw = w - 52;
        const iy = cy + 18;
        ctx.save();
        ctx.globalAlpha *= r;
        ctx.setLineDash([10, 7]);
        ctx.lineDashOffset = -t * 14;
        ctx.strokeStyle = rgba(c, 0.85);
        ctx.lineWidth = 2;
        roundRect(ctx, ix, iy, iw, innerH, 12);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = rgba(c, 0.07);
        ctx.fill();
        // corner tag
        ctx.font = font(theme.fonts.mono, 22, 700);
        const tag = this.o.inner.label;
        const tw = ctx.measureText(tag).width + 18;
        roundRect(ctx, ix + 16, iy - 16, tw, 32, 8);
        ctx.fillStyle = theme.panel;
        ctx.fill();
        ctx.fillStyle = c;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(tag, ix + 25, iy + 1);
        ctx.textBaseline = 'alphabetic';
        ctx.textAlign = 'center';
        ctx.fillStyle = theme.text;
        ctx.font = font(theme.fonts.mono, 28, 400);
        this.o.inner.lines.forEach((l, i) => ctx.fillText(l, this.cx, iy + 60 + i * 34));
        ctx.restore();
      }
    }
  }

  private drawSegments(ctx: Ctx, t: number) {
    const { x, y, w, h } = this.o;
    const segs = this.o.segments!;
    const sw = w / segs.length;
    const c = this.color;
    segs.forEach((seg, i) => {
      const r = this.segReveal[i].value(t);
      if (r <= 0) return;
      const g = this.segGlow[i].value(t);
      const sx = x + i * sw;
      ctx.save();
      ctx.globalAlpha *= r;
      if (g > 0) {
        roundRect(ctx, sx + 8, y + 8, sw - 16, h - 16, 12);
        ctx.fillStyle = rgba(c, 0.16 * g);
        ctx.fill();
      }
      if (i > 0) {
        ctx.strokeStyle = rgba(c, 0.3);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(sx, y + 18);
        ctx.lineTo(sx, y + h - 18);
        ctx.stroke();
      }
      ctx.textAlign = 'center';
      ctx.fillStyle = theme.text;
      ctx.font = font(theme.fonts.mono, this.o.titleSize ?? 34, 700);
      const mid = y + h / 2;
      if (seg.icon) {
        ctx.font = font(theme.fonts.mono, this.o.titleSize ?? 34, 700);
        const tw = ctx.measureText(seg.title).width;
        drawIcon(ctx, seg.icon, sx + sw / 2 - tw / 2 - 26, seg.sub ? mid - 18 : mid, 30, c);
        ctx.fillText(seg.title, sx + sw / 2 + 18, seg.sub ? mid - 6 : mid + 12);
      } else {
        ctx.fillText(seg.title, sx + sw / 2, seg.sub ? mid - 6 : mid + 12);
      }
      if (seg.sub) {
        ctx.fillStyle = theme.muted;
        ctx.font = font(theme.fonts.mono, this.o.subSize ?? 26, 400);
        ctx.fillText(seg.sub, sx + sw / 2, mid + 34);
      }
      ctx.restore();
    });
  }
}

function lerpHex(a: string, b: string, k: number): string {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const ch = (s: number) => Math.round(lerp((pa >> s) & 255, (pb >> s) & 255, k));
  return `rgb(${ch(16)}, ${ch(8)}, ${ch(0)})`;
}
