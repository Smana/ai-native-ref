// Renders a scene to MP4 (or PNG stills) in headless Chromium, frame by frame,
// and pipes the frames into ffmpeg. `--serve` starts the interactive preview instead.
//
//   tsx scripts/render.ts [--scene agent-factory] [--out out/x.mp4] [--from 0] [--to 11]
//   tsx scripts/render.ts --still 5,9.5        # PNGs in out/
//   tsx scripts/render.ts --serve [--port 5173]
//
// Optional logos: assets/icons/<name>.svg replaces the built-in glyph of that name.

import { createServer, type Server } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { extname, join, resolve, dirname } from 'node:path';
import { chromium } from 'playwright';

const root = resolve(__dirname, '..');

function args() {
  const a = process.argv.slice(2);
  const get = (k: string) => {
    const i = a.indexOf(`--${k}`);
    return i >= 0 ? (a[i + 1] && !a[i + 1].startsWith('--') ? a[i + 1] : '') : undefined;
  };
  const scene = get('scene') || 'agent-factory';
  return {
    scene,
    out: get('out') || join(root, 'out', `${scene}.mp4`),
    from: Number(get('from') ?? 0),
    to: get('to') !== undefined ? Number(get('to')) : undefined,
    still: get('still'),
    serve: get('serve') !== undefined,
    port: Number(get('port') || 5173),
    logo: resolve(root, get('logo') || '../../website/static/images/ogenki-mark-white.svg'),
    crf: Number(get('crf') || 18),
  };
}

const types: Record<string, string> = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.woff2': 'font/woff2',
};

function serve(port: number, logo: string): Promise<Server> {
  const server = createServer(async (req, res) => {
    const path = decodeURIComponent((req.url || '/').split('?')[0]);
    const file = path === '/assets/logo.svg' ? logo : join(root, path === '/' ? 'index.html' : path);
    if (!file.startsWith(root) && file !== logo) {
      res.writeHead(403).end();
      return;
    }
    try {
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' }).end(body);
    } catch {
      res.writeHead(404).end();
    }
  });
  return new Promise((ok) => server.listen(port, '127.0.0.1', () => ok(server)));
}

async function main() {
  const o = args();
  const server = await serve(o.port, o.logo);
  const base = `http://127.0.0.1:${o.port}/`;

  if (o.serve) {
    console.log(`preview: ${base}?preview&scene=${o.scene}   (Ctrl+C to stop)`);
    return;
  }

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.error('page error:', e.message));
  await page.goto(base);
  await page.waitForFunction(() => (window as any).mcReady === true);
  const info: { duration: number; fps: number; width: number; height: number } = await page.evaluate(
    (name) => (window as any).mc.init(name),
    o.scene,
  );

  await mkdir(dirname(o.out), { recursive: true });

  if (o.still !== undefined) {
    const times = (o.still || '0').split(',').map(Number);
    const urls: string[] = await page.evaluate((ts) => (window as any).mc.frames(ts), times);
    for (let i = 0; i < times.length; i++) {
      const file = join(root, 'out', `${o.scene}-${times[i].toFixed(2)}s.png`);
      await import('node:fs/promises').then((fs) => fs.writeFile(file, Buffer.from(urls[i].split(',')[1], 'base64')));
      console.log(file);
    }
  } else {
    const end = Math.min(o.to ?? info.duration, info.duration);
    const first = Math.round(o.from * info.fps);
    const last = Math.round(end * info.fps); // exclusive: the frame at `end` equals frame 0 of the loop
    const ff = spawn(
      'ffmpeg',
      ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(info.fps), '-c:v', 'png', '-i', '-',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', String(o.crf), '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', '-an', o.out],
      { stdio: ['pipe', 'inherit', 'inherit'] },
    );
    const done = new Promise<void>((ok, ko) => ff.on('close', (c) => (c === 0 ? ok() : ko(new Error(`ffmpeg exited ${c}`)))));
    const batch = 15;
    for (let f = first; f < last; f += batch) {
      const times = Array.from({ length: Math.min(batch, last - f) }, (_, i) => (f + i) / info.fps);
      const urls: string[] = await page.evaluate((ts) => (window as any).mc.frames(ts), times);
      for (const u of urls) {
        if (!ff.stdin.write(Buffer.from(u.split(',')[1], 'base64'))) await new Promise((r) => ff.stdin.once('drain', r));
      }
      process.stdout.write(`\rframe ${Math.min(f + batch, last) - first}/${last - first}`);
    }
    ff.stdin.end();
    await done;
    console.log(`\n${o.out}`);
  }

  await browser.close();
  server.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
