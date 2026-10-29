import { Element, type Ctx } from '../engine/scene.js';
import { Track, easing, lerp } from '../engine/tween.js';
import { font, rgba } from '../engine/draw.js';
import { theme } from './theme.js';

export interface TitleCardOptions {
  logo: CanvasImageSource | null;
  logoAspect: number; // height / width
  mark?: CanvasImageSource | null; // product mark, drawn left of the centred title
  title: string;
  subtitle: string[];
  kicker?: string;
  headerRight?: string;
  accent?: string;
}

/**
 * The hook card. `dock` animates it from a centred title card (0) to a
 * compact header (1); `details` fades the subtitle and kicker.
 * Frame 0 shows it centred, so a clip that docks it back at the end loops cleanly.
 */
export class TitleCard extends Element {
  readonly dock = new Track(0);
  readonly details = new Track(1);
  readonly headerRight = new Track(0);

  constructor(readonly o: TitleCardOptions) {
    super(true);
    this.z = 60;
  }

  dockAt(at: number, dur = 1.0): this {
    this.dock.to(1, at, dur, easing.inOutCubic);
    this.details.to(0, at, dur * 0.4);
    this.headerRight.to(1, at + dur * 0.6, 0.5);
    return this;
  }

  undockAt(at: number, dur = 1.0): this {
    this.headerRight.to(0, at, 0.3);
    this.dock.to(0, at, dur, easing.inOutCubic);
    this.details.to(1, at + dur * 0.6, dur * 0.4);
    return this;
  }

  draw(ctx: Ctx, t: number): void {
    const W = theme.width;
    const k = this.dock.value(t);
    const accent = this.o.accent ?? theme.cyan;

    // logo
    const ls = lerp(190, 58, k);
    const lh = ls * this.o.logoAspect;
    const lcx = lerp(W / 2, 50 + 58 / 2, k);
    const lcy = lerp(400, 78, k);
    if (this.o.logo) ctx.drawImage(this.o.logo, lcx - ls / 2, lcy - lh / 2, ls, lh);

    // title
    const size = lerp(92, 44, k);
    ctx.font = font(theme.fonts.mono, size, 800);
    const tw = ctx.measureText(this.o.title).width;
    const ms = this.o.mark ? size * 1.05 : 0; // mark size, square
    const gap = ms ? 26 : 0;
    const tx = lerp(W / 2 - (tw + ms + gap) / 2 + ms + gap, 126, k);
    const ty = lerp(620, 80, k);
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = theme.text;
    ctx.fillText(this.o.title, tx, ty);
    if (this.o.mark && k < 1) {
      ctx.save();
      ctx.globalAlpha *= 1 - k;
      ctx.drawImage(this.o.mark, tx - gap - ms, ty - ms / 2, ms, ms);
      ctx.restore();
    }

    // underline accent
    const ul = lerp(140, 0, k);
    if (ul > 1) {
      ctx.fillStyle = accent;
      ctx.fillRect(W / 2 - ul / 2, ty + size * 0.72, ul, 6);
    }

    // subtitle + kicker
    const d = this.details.value(t);
    if (d > 0) {
      ctx.save();
      ctx.globalAlpha *= d;
      ctx.textAlign = 'center';
      ctx.font = font(theme.fonts.sans, 46, 500);
      ctx.fillStyle = theme.muted;
      this.o.subtitle.forEach((line, i) => ctx.fillText(line, W / 2, 790 + i * 60));
      if (this.o.kicker) {
        ctx.font = font(theme.fonts.mono, 26, 600);
        ctx.fillStyle = rgba(accent, 0.9);
        ctx.fillText(this.o.kicker, W / 2, 790 + this.o.subtitle.length * 60 + 70);
      }
      ctx.restore();
    }

    // header right
    const hr = this.headerRight.value(t);
    if (hr > 0 && this.o.headerRight) {
      ctx.save();
      ctx.globalAlpha *= hr;
      ctx.textAlign = 'right';
      ctx.font = font(theme.fonts.mono, 24, 500);
      ctx.fillStyle = theme.muted;
      ctx.fillText(this.o.headerRight, W - 50, 82);
      ctx.restore();
    }
  }
}

/** Dark gradient with a faint dot grid whose visibility is a track. */
export function background(grid: Track) {
  return (ctx: Ctx, t: number) => {
    const W = theme.width;
    const H = theme.height;
    ctx.fillStyle = theme.bg;
    ctx.fillRect(0, 0, W, H);
    const g = ctx.createRadialGradient(W / 2, H * 0.42, 50, W / 2, H * 0.42, H * 0.75);
    g.addColorStop(0, theme.bgGlow);
    g.addColorStop(1, theme.bg);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    const a = grid.value(t);
    if (a > 0) {
      ctx.fillStyle = rgba(theme.grid, a);
      for (let x = 30; x < W; x += 40) for (let y = 140; y < H - 160; y += 40) ctx.fillRect(x, y, 2, 2);
    }
  };
}
