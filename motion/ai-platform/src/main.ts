// Browser entry point. The render script (or a human, in preview mode) loads
// index.html, which calls window.mc.init(sceneName).

import type { Scene } from './engine/scene.js';
import { scenes } from './scenes/index.js';
import { theme } from './components/theme.js';
import { ICON_NAMES, iconImages } from './components/Icon.js';

export interface Assets {
  logo: HTMLImageElement | null;
  logoAspect: number;
  mark: HTMLImageElement | null;
}

async function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

async function loadFonts() {
  const specs = [
    `400 24px ${theme.fonts.mono}`,
    `700 24px ${theme.fonts.mono}`,
    `800 24px ${theme.fonts.mono}`,
    `500 24px ${theme.fonts.sans}`,
    `600 24px ${theme.fonts.sans}`,
  ];
  await Promise.all(specs.map((s) => document.fonts.load(s).catch(() => [])));
  await document.fonts.ready;
}

class Player {
  scene!: Scene;
  ctx!: CanvasRenderingContext2D;
  canvas!: HTMLCanvasElement;

  async init(name: string) {
    const make = scenes[name];
    if (!make) throw new Error(`unknown scene "${name}"; have: ${Object.keys(scenes).join(', ')}`);
    await loadFonts();
    const logo = await loadImage('assets/logo.svg');
    const mark = await loadImage('assets/maku-mark.svg');
    await Promise.all(
      ICON_NAMES.map(async (n) => {
        const color = await loadImage(`assets/icons/${n}.color.svg`);
        if (color) return iconImages.set(n, { img: color, tint: false });
        const mono = await loadImage(`assets/icons/${n}.svg`);
        if (mono) iconImages.set(n, { img: mono, tint: true });
      }),
    );
    const logoAspect = logo ? logo.naturalHeight / logo.naturalWidth || 396 / 448 : 396 / 448;
    this.scene = make({ logo, logoAspect, mark });
    this.canvas = document.querySelector('canvas')!;
    this.canvas.width = this.scene.width;
    this.canvas.height = this.scene.height;
    this.ctx = this.canvas.getContext('2d')!;
    this.render(0);
    return { duration: this.scene.duration, fps: this.scene.fps, width: this.scene.width, height: this.scene.height };
  }

  render(t: number) {
    this.scene.render(this.ctx, t);
  }

  /** Render the given times and return PNG data URLs. */
  frames(times: number[]): string[] {
    return times.map((t) => {
      this.render(t);
      return this.canvas.toDataURL('image/png');
    });
  }

  /** Interactive preview: play/pause with space, scrub with the slider. */
  preview() {
    const bar = document.getElementById('bar')!;
    bar.hidden = false;
    const slider = document.getElementById('scrub') as HTMLInputElement;
    const label = document.getElementById('time')!;
    slider.max = String(this.scene.duration);
    let playing = true;
    let t0 = performance.now();
    let t = 0;
    const tick = (now: number) => {
      if (playing) {
        t = ((now - t0) / 1000) % this.scene.duration;
        slider.value = String(t);
      }
      label.textContent = `${t.toFixed(2)} s`;
      this.render(t);
      requestAnimationFrame(tick);
    };
    slider.oninput = () => {
      playing = false;
      t = Number(slider.value);
    };
    document.onkeydown = (e) => {
      if (e.code !== 'Space') return;
      playing = !playing;
      t0 = performance.now() - t * 1000;
    };
    requestAnimationFrame(tick);
  }
}

declare global {
  interface Window {
    mc: Player;
  }
}

window.mc = new Player();
