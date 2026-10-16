import { Element, type Ctx } from '../engine/scene.js';
import { Track, easing } from '../engine/tween.js';
import { font, rgba, roundRect } from '../engine/draw.js';
import { theme } from './theme.js';
import { drawIcon, type IconName } from './Icon.js';

export interface RegionOptions {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  color?: string;
  dashed?: boolean;
  icon?: IconName;
  labelAlign?: 'left' | 'right';
}

/** A labelled area grouping nodes (a half of the platform, a cluster...). */
export class Region extends Element {
  /** 0..1, the border draws around the region. */
  readonly trace = new Track(0);

  constructor(readonly o: RegionOptions) {
    super(false);
    this.z = 1;
  }

  override show(at: number, dur = 0.9): this {
    this.opacity.to(1, at, 0.3);
    this.trace.to(1, at, dur, easing.inOutCubic);
    return this;
  }

  draw(ctx: Ctx, t: number): void {
    const { x, y, w, h, label } = this.o;
    const c = this.o.color ?? theme.cyan;
    const k = this.trace.value(t);
    const perimeter = 2 * (w + h);

    roundRect(ctx, x, y, w, h, 26);
    ctx.fillStyle = rgba(c, 0.035 * k);
    ctx.fill();
    ctx.strokeStyle = rgba(c, 0.45);
    ctx.lineWidth = 2;
    ctx.setLineDash(this.o.dashed ? [12, 9] : [perimeter * k, perimeter]);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.globalAlpha *= Math.min(1, k * 2);
    ctx.font = font(theme.fonts.mono, 24, 700);
    ctx.fillStyle = c;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    const text = label.toUpperCase().split('').join('\u200a');
    const iw = this.o.icon ? 44 : 0;
    const tw = ctx.measureText(text).width + iw;
    const lx = this.o.labelAlign === 'right' ? x + w - 26 - tw : x + 26;
    if (this.o.icon) drawIcon(ctx, this.o.icon, lx + 14, y + 32, 30, c);
    ctx.fillText(text, lx + iw, y + 32);
  }
}
