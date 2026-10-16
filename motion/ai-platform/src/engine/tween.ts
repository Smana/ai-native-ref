// Deterministic keyframe tracks: every property is a pure function of time,
// so any frame can be rendered in any order (scrubbing, partial renders).

export type Ease = (x: number) => number;

export const easing = {
  linear: (x: number) => x,
  inCubic: (x: number) => x * x * x,
  outCubic: (x: number) => 1 - Math.pow(1 - x, 3),
  inOutCubic: (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  inOutSine: (x: number) => -(Math.cos(Math.PI * x) - 1) / 2,
  outBack: (x: number) => {
    const c1 = 1.4;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
  },
};

interface Segment {
  t0: number;
  t1: number;
  to: number;
  ease: Ease;
}

export class Track {
  private segments: Segment[] = [];

  constructor(private readonly initial = 0) {}

  /** Animate to `value`, starting at `at` seconds, over `dur` seconds. */
  to(value: number, at: number, dur = 0.5, ease: Ease = easing.inOutCubic): this {
    this.segments.push({ t0: at, t1: at + Math.max(dur, 1e-6), to: value, ease });
    this.segments.sort((a, b) => a.t0 - b.t0);
    return this;
  }

  /** Jump to `value` at `at`. */
  set(value: number, at: number): this {
    return this.to(value, at, 0, easing.linear);
  }

  value(t: number): number {
    let v = this.initial;
    for (const s of this.segments) {
      if (t >= s.t1) {
        v = s.to;
        continue;
      }
      if (t <= s.t0) break;
      return v + (s.to - v) * s.ease((t - s.t0) / (s.t1 - s.t0));
    }
    return v;
  }
}

export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
