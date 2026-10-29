import type { Ctx } from '../engine/scene.js';

/**
 * Icons are generic glyphs drawn with canvas paths. Editable copies live in
 * assets/icons/glyphs/. To override one, drop a file into assets/icons/:
 *   <name>.svg        monochrome, tinted with the node's colour
 *   <name>.color.svg  full-colour logo, drawn as-is
 */
export const iconImages = new Map<string, { img: CanvasImageSource; tint: boolean }>();

const tintCanvas = document.createElement('canvas');

export const ICON_NAMES = [
  'person', 'github', 'tag', 'eye', 'factory', 'cube', 'shield', 'key', 'branch', 'brain', 'tools', 'cluster', 'chart',
  'scope', 'scale', 'search', 'checklist',
] as const;
export type IconName = (typeof ICON_NAMES)[number];

export function drawIcon(ctx: Ctx, name: IconName, cx: number, cy: number, size: number, color: string) {
  const over = iconImages.get(name);
  if (over) {
    if (!over.tint) {
      ctx.drawImage(over.img, cx - size / 2, cy - size / 2, size, size);
      return;
    }
    const px = Math.ceil(size * 2);
    tintCanvas.width = px;
    tintCanvas.height = px;
    const tc = tintCanvas.getContext('2d')!;
    tc.drawImage(over.img, 0, 0, px, px);
    tc.globalCompositeOperation = 'source-in';
    tc.fillStyle = color;
    tc.fillRect(0, 0, px, px);
    ctx.drawImage(tintCanvas, cx - size / 2, cy - size / 2, size, size);
    return;
  }
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(size / 24, size / 24);
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  glyphs[name](ctx);
  ctx.restore();
}

// Every glyph is drawn in a 24×24 box centred on the origin.
const glyphs: Record<IconName, (ctx: Ctx) => void> = {
  person(ctx) {
    ctx.beginPath();
    ctx.arc(0, -4, 4.5, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-9, 10);
    ctx.quadraticCurveTo(-9, 2, 0, 2);
    ctx.quadraticCurveTo(9, 2, 9, 10);
    ctx.stroke();
  },
  github(ctx) {
    // A generic repository card: folder with a commit dot row.
    ctx.beginPath();
    ctx.roundRect(-10, -8, 20, 16, 3);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-10, -3);
    ctx.lineTo(10, -3);
    ctx.stroke();
    for (const x of [-5, 0, 5]) {
      ctx.beginPath();
      ctx.arc(x, 2.5, 1.6, 0, Math.PI * 2);
      ctx.fill();
    }
  },
  tag(ctx) {
    ctx.beginPath();
    ctx.moveTo(-10, -6);
    ctx.lineTo(0, -6);
    ctx.lineTo(10, 4);
    ctx.lineTo(4, 10);
    ctx.lineTo(-6, 0);
    ctx.lineTo(-10, 0);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(-6, -3, 1.6, 0, Math.PI * 2);
    ctx.fill();
  },
  eye(ctx) {
    ctx.beginPath();
    ctx.moveTo(-11, 0);
    ctx.quadraticCurveTo(0, -11, 11, 0);
    ctx.quadraticCurveTo(0, 11, -11, 0);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, 3.5, 0, Math.PI * 2);
    ctx.fill();
  },
  factory(ctx) {
    ctx.beginPath();
    ctx.moveTo(-10, 9);
    ctx.lineTo(-10, -2);
    ctx.lineTo(-3, 2);
    ctx.lineTo(-3, -2);
    ctx.lineTo(4, 2);
    ctx.lineTo(4, -2);
    ctx.lineTo(10, 2);
    ctx.lineTo(10, 9);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-8, -2);
    ctx.lineTo(-8, -9);
    ctx.lineTo(-5, -9);
    ctx.lineTo(-5, -4);
    ctx.stroke();
  },
  cube(ctx) {
    ctx.beginPath();
    ctx.moveTo(0, -10);
    ctx.lineTo(9, -5);
    ctx.lineTo(9, 5);
    ctx.lineTo(0, 10);
    ctx.lineTo(-9, 5);
    ctx.lineTo(-9, -5);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-9, -5);
    ctx.lineTo(0, 0);
    ctx.lineTo(9, -5);
    ctx.moveTo(0, 0);
    ctx.lineTo(0, 10);
    ctx.stroke();
  },
  shield(ctx) {
    ctx.beginPath();
    ctx.moveTo(0, -10);
    ctx.lineTo(9, -6);
    ctx.quadraticCurveTo(9, 6, 0, 10);
    ctx.quadraticCurveTo(-9, 6, -9, -6);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-4, 0);
    ctx.lineTo(-1, 3);
    ctx.lineTo(4, -3);
    ctx.stroke();
  },
  key(ctx) {
    ctx.beginPath();
    ctx.arc(-5, 0, 5, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(11, 0);
    ctx.moveTo(8, 0);
    ctx.lineTo(8, 4);
    ctx.moveTo(11, 0);
    ctx.lineTo(11, 3);
    ctx.stroke();
  },
  branch(ctx) {
    ctx.beginPath();
    ctx.arc(-6, -7, 2.8, 0, Math.PI * 2);
    ctx.arc(-6, 7, 2.8, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(6, -4, 2.8, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-6, -4);
    ctx.lineTo(-6, 4);
    ctx.moveTo(6, -1);
    ctx.quadraticCurveTo(6, 4, -3, 5);
    ctx.stroke();
  },
  brain(ctx) {
    // Sparkle: a generic "model" mark.
    ctx.beginPath();
    ctx.moveTo(0, -11);
    ctx.quadraticCurveTo(1.5, -1.5, 11, 0);
    ctx.quadraticCurveTo(1.5, 1.5, 0, 11);
    ctx.quadraticCurveTo(-1.5, 1.5, -11, 0);
    ctx.quadraticCurveTo(-1.5, -1.5, 0, -11);
    ctx.closePath();
    ctx.fill();
  },
  tools(ctx) {
    ctx.beginPath();
    ctx.moveTo(-9, 9);
    ctx.lineTo(3, -3);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(5, -5, 4, Math.PI * 0.25, Math.PI * 1.75);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-9, -9);
    ctx.lineTo(9, 9);
    ctx.stroke();
  },
  cluster(ctx) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i - Math.PI / 6;
      const x = Math.cos(a) * 10.5;
      const y = Math.sin(a) * 10.5;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
    for (const [x, y] of [[-3.5, -3], [3.5, -3], [0, 3.5]]) {
      ctx.beginPath();
      ctx.arc(x, y, 1.8, 0, Math.PI * 2);
      ctx.fill();
    }
  },
  chart(ctx) {
    ctx.beginPath();
    ctx.moveTo(-10, 10);
    ctx.lineTo(10, 10);
    ctx.stroke();
    for (const [x, h] of [[-7, 6], [-1, 12], [5, 9]]) ctx.fillRect(x, 10 - h, 4, h);
  },
  scope(ctx) {
    ctx.beginPath();
    ctx.arc(0, 0, 8, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, -11);
    ctx.lineTo(0, -5);
    ctx.moveTo(0, 5);
    ctx.lineTo(0, 11);
    ctx.moveTo(-11, 0);
    ctx.lineTo(-5, 0);
    ctx.moveTo(5, 0);
    ctx.lineTo(11, 0);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, 1.8, 0, Math.PI * 2);
    ctx.fill();
  },
  scale(ctx) {
    ctx.beginPath();
    ctx.moveTo(0, -10);
    ctx.lineTo(0, 10);
    ctx.moveTo(-6, 10);
    ctx.lineTo(6, 10);
    ctx.moveTo(-10, -6);
    ctx.lineTo(10, -6);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-10, -6);
    ctx.lineTo(-13.5, 2);
    ctx.lineTo(-6.5, 2);
    ctx.closePath();
    ctx.moveTo(10, -6);
    ctx.lineTo(6.5, 2);
    ctx.lineTo(13.5, 2);
    ctx.closePath();
    ctx.stroke();
  },
  search(ctx) {
    ctx.beginPath();
    ctx.arc(-2.5, -2.5, 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(2.5, 2.5);
    ctx.lineTo(10, 10);
    ctx.stroke();
  },
  checklist(ctx) {
    for (const y of [-7, 0, 7]) {
      ctx.beginPath();
      ctx.moveTo(-10, y + 0.5);
      ctx.lineTo(-7.5, y + 3);
      ctx.lineTo(-4, y - 2.5);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(10, y);
      ctx.stroke();
    }
  },
};
