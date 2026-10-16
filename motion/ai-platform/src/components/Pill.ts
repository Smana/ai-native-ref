import { Element, type Ctx } from '../engine/scene.js';
import { Track, easing, lerp } from '../engine/tween.js';
import { font, rgba, roundRect } from '../engine/draw.js';
import { theme } from './theme.js';

export interface PillOptions {
  x: number;
  y: number;
  text: string;
  color?: string;
  /** Small leading tag, e.g. "v2". */
  tag?: string;
  dashed?: boolean;
  size?: number;
  align?: 'left' | 'center' | 'right';
}

/** A small label chip, attached to a node or floating on the diagram. */
export class Pill extends Element {
  readonly pop = new Track(0);

  constructor(readonly o: PillOptions) {
    super(false);
    this.z = 20;
  }

  override show(at: number, dur = 0.45): this {
    this.opacity.to(1, at, dur * 0.6, easing.outCubic);
    this.pop.to(1, at, dur, easing.outBack);
    return this;
  }

  draw(ctx: Ctx, t: number): void {
    const c = this.o.color ?? theme.cyan;
    const size = this.o.size ?? 24;
    const padX = 16;
    const h = size + 20;
    ctx.font = font(theme.fonts.mono, size, 700);
    const textW = ctx.measureText(this.o.text).width;
    let tagW = 0;
    if (this.o.tag) {
      ctx.font = font(theme.fonts.mono, size - 4, 800);
      tagW = ctx.measureText(this.o.tag).width + 16 + 10;
    }
    const w = textW + tagW + padX * 2;
    const align = this.o.align ?? 'center';
    const x0 = align === 'center' ? this.o.x - w / 2 : align === 'right' ? this.o.x - w : this.o.x;
    const y0 = this.o.y - h / 2;

    const s = lerp(0.7, 1, this.pop.value(t));
    const ax = x0 + w / 2;
    ctx.translate(ax, this.o.y);
    ctx.scale(s, s);
    ctx.translate(-ax, -this.o.y);

    roundRect(ctx, x0, y0, w, h, h / 2);
    ctx.fillStyle = theme.bg;
    ctx.fill();
    ctx.fillStyle = rgba(c, 0.14);
    ctx.fill();
    ctx.strokeStyle = c;
    ctx.lineWidth = 2;
    if (this.o.dashed) ctx.setLineDash([7, 5]);
    ctx.stroke();
    ctx.setLineDash([]);

    let x = x0 + padX;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    if (this.o.tag) {
      ctx.font = font(theme.fonts.mono, size - 4, 800);
      const tw = ctx.measureText(this.o.tag).width + 16;
      roundRect(ctx, x - 6, this.o.y - (size - 2) / 2 - 2, tw, size + 2, 6);
      ctx.fillStyle = c;
      ctx.fill();
      ctx.fillStyle = theme.bg;
      ctx.fillText(this.o.tag, x + 2, this.o.y + 1);
      x += tw + 4;
    }
    ctx.font = font(theme.fonts.mono, size, 700);
    ctx.fillStyle = c;
    ctx.fillText(this.o.text, x, this.o.y + 1);
  }
}
