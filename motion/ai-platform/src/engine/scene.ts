import { Track, easing } from './tween.js';

export type Ctx = CanvasRenderingContext2D;

/** How much a dimmed element fades (0 = no change, 1 = invisible). */
export const DIM_STRENGTH = 0.74;

export abstract class Element {
  readonly opacity: Track;
  readonly dim = new Track(0);
  /** Elements in a group share a master opacity (used for crossfades). */
  group = 'default';
  z = 0;

  constructor(visible = false) {
    this.opacity = new Track(visible ? 1 : 0);
  }

  alpha(t: number): number {
    return this.opacity.value(t) * (1 - DIM_STRENGTH * this.dim.value(t));
  }

  show(at: number, dur = 0.5): this {
    this.opacity.to(1, at, dur, easing.outCubic);
    return this;
  }

  hide(at: number, dur = 0.5): this {
    this.opacity.to(0, at, dur, easing.inOutCubic);
    return this;
  }

  dimAt(at: number, dur = 0.4): this {
    this.dim.to(1, at, dur);
    return this;
  }

  undimAt(at: number, dur = 0.4): this {
    this.dim.to(0, at, dur);
    return this;
  }

  abstract draw(ctx: Ctx, t: number): void;
}

export interface SceneOptions {
  width: number;
  height: number;
  fps: number;
  duration: number;
  background: (ctx: Ctx, t: number) => void;
  /** Shift every element, to reuse a layout on a canvas of another size. */
  offset?: [number, number];
}

export class Scene {
  readonly elements: Element[] = [];
  readonly groups = new Map<string, Track>();

  constructor(readonly opts: SceneOptions) {}

  get width() {
    return this.opts.width;
  }
  get height() {
    return this.opts.height;
  }
  get fps() {
    return this.opts.fps;
  }
  get duration() {
    return this.opts.duration;
  }

  add<T extends Element>(e: T, group?: string): T {
    if (group) e.group = group;
    this.elements.push(e);
    return e;
  }

  group(name: string): Track {
    let tr = this.groups.get(name);
    if (!tr) {
      tr = new Track(1);
      this.groups.set(name, tr);
    }
    return tr;
  }

  render(ctx: Ctx, t: number): void {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    this.opts.background(ctx, t);
    if (this.opts.offset) ctx.translate(this.opts.offset[0], this.opts.offset[1]);
    const ordered = [...this.elements].sort((a, b) => a.z - b.z);
    for (const e of ordered) {
      const g = this.groups.get(e.group)?.value(t) ?? 1;
      const a = e.alpha(t) * g;
      if (a <= 0.002) continue;
      ctx.save();
      ctx.globalAlpha = a;
      e.draw(ctx, t);
      ctx.restore();
    }
    ctx.restore();
  }
}
