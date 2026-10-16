import { Element, type Ctx } from '../engine/scene.js';
import { Track, easing } from '../engine/tween.js';
import { font, parseAccents, rgba, roundRect, runsWidth, wrapRuns } from '../engine/draw.js';
import { theme } from './theme.js';

interface Cue {
  text: string;
  from: number;
  to: number;
  accent: string;
}

export interface CaptionOptions {
  /** Vertical centre of the caption band. */
  y: number;
  maxWidth?: number;
  size?: number;
}

/**
 * Burned-in captions. `cue(text, from, to)` shows one caption; wrap words in
 * **double asterisks** to colour them with the cue's accent.
 */
export class Caption extends Element {
  private cues: Cue[] = [];
  private readonly fade = 0.35;

  constructor(readonly o: CaptionOptions) {
    super(true);
    this.z = 50;
  }

  cue(text: string, from: number, to: number, accent = theme.cyan): this {
    this.cues.push({ text, from, to, accent });
    return this;
  }

  draw(ctx: Ctx, t: number): void {
    const size = this.o.size ?? 42;
    const maxW = this.o.maxWidth ?? 960;
    const lh = size * 1.3;
    for (const c of this.cues) {
      if (t < c.from || t > c.to) continue;
      const a = Math.min(1, (t - c.from) / this.fade, (c.to - t) / this.fade);
      const rise = (1 - easing.outCubic(Math.min(1, (t - c.from) / 0.5))) * 14;
      ctx.save();
      ctx.globalAlpha *= a;
      ctx.font = font(theme.fonts.sans, size, 600);
      const lines = wrapRuns(ctx, parseAccents(c.text), maxW);
      const blockH = lines.length * lh;
      const top = this.o.y - blockH / 2 + rise;

      const bw = Math.max(...lines.map((l) => runsWidth(ctx, l))) + 64;
      roundRect(ctx, (theme.width - bw) / 2, top - 22, bw, blockH + 44, 22);
      ctx.fillStyle = rgba(theme.bg, 0.86);
      ctx.fill();
      ctx.strokeStyle = rgba(c.accent, 0.35);
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.textBaseline = 'middle';
      ctx.textAlign = 'left';
      lines.forEach((line, i) => {
        let x = (theme.width - runsWidth(ctx, line)) / 2;
        const y = top + lh * (i + 0.5);
        for (const r of line) {
          ctx.fillStyle = r.accent ? c.accent : theme.text;
          ctx.fillText(r.text, x, y);
          x += ctx.measureText(r.text).width;
        }
      });
      ctx.restore();
    }
  }
}

/** A simple text block with its own opacity (titles, URLs, footers). */
export class Text extends Element {
  readonly rise = new Track(0);

  constructor(
    readonly o: {
      x: number;
      y: number;
      text: string;
      size: number;
      color?: string;
      weight?: number;
      family?: 'mono' | 'sans';
      align?: CanvasTextAlign;
    },
  ) {
    super(false);
    this.z = 40;
  }

  draw(ctx: Ctx, _t: number): void {
    ctx.font = font(theme.fonts[this.o.family ?? 'mono'], this.o.size, this.o.weight ?? 600);
    ctx.fillStyle = this.o.color ?? theme.text;
    ctx.textAlign = this.o.align ?? 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(this.o.text, this.o.x, this.o.y);
  }
}
