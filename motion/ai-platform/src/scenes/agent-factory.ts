// Agent Factory: one task end to end, built up a few nodes per beat.

import { Scene } from '../engine/scene.js';
import { Track } from '../engine/tween.js';
import { Caption, Edge, Node, Pill, Region, Text, TitleCard, background, theme } from '../components/index.js';
import type { Assets } from '../main.js';
import { beats, duration, labels as L, title as T } from './agent-factory.storyboard.js';

const C = theme.cyan; // what runs today
const H = theme.neutral; // humans and GitHub

export const DURATION = duration;

export function agentFactory(assets: Assets): Scene {
  const grid = new Track(0);
  const scene = new Scene({
    width: theme.width,
    height: theme.height,
    fps: theme.fps,
    duration: DURATION,
    background: background(grid),
  });

  // ---- layout ---------------------------------------------------------------
  // The developer and GitHub on the top row, outside the cluster. Everything the
  // factory runs sits inside the Kubernetes region below: the planner, the room
  // and Maku on one row, the run under them.
  const col1 = 30;
  const col3 = 650;
  const colW = 380;
  const rowY = 390;
  const rowW = 290;

  const cluster = new Region({ x: 14, y: 300, w: 1026, h: 715, label: L.cluster, color: C, icon: 'cluster', labelAlign: 'right' });

  const developer = new Node({ x: col1, y: 130, w: colW, h: 140, title: L.developer.title, sub: [L.developer.sub], subSize: 26, color: H, icon: 'person' });
  const github = new Node({ x: col3, y: 130, w: colW, h: 140, title: L.github.title, sub: [L.github.sub], color: H, icon: 'github' });
  const planner = new Node({ x: 30, y: rowY, w: rowW, h: 140, title: L.planner.title, sub: L.planner.sub, subSize: 26, color: C, icon: 'checklist' });
  const room = new Node({ x: 370, y: rowY, w: 270, h: 140, title: L.room.title, sub: [L.room.sub], color: C, icon: 'eye' });
  const factory = new Node({ x: 760, y: rowY, w: 270, h: 140, title: L.factory.title, sub: [L.factory.sub], color: C, icon: 'factory' });
  const run = new Node({
    x: 260, y: 585, w: 560, h: 220, title: L.run.title, color: C, icon: 'cube',
    inner: { label: L.run.sandbox, lines: [L.run.inside] },
  });
  const gateway = new Node({ x: 260, y: 865, w: 560, h: 130, title: L.gateway.title, sub: [L.gateway.sub], color: C, icon: 'key' });
  const upstream = new Node({
    x: 30, y: 1040, w: 1020, h: 120, title: '', color: C,
    segments: [
      { ...L.models, icon: 'brain' },
      { ...L.tools, icon: 'tools' },
      { ...L.token, icon: 'shield' },
    ],
  });

  // one sentence down, the plan back up: two lanes, since a packet runs one way
  const eAsk = new Edge({ points: [[120, 270], [120, rowY]], color: H });
  const ePlan = new Edge({ points: [[230, rowY], [230, 270]], color: C, label: { text: L.edges.ask, x: 248, y: 330, align: 'left' } });
  const eFile = new Edge({ points: [[410, 175], [650, 175]], color: H, label: { text: L.edges.file, x: 530, y: 150 } });
  // the review pill (38 px tall) rides at y 193–231, clear of the label below it
  const eReview = new Edge({ points: [[410, 212], [650, 212]], color: H, label: { text: L.edges.review, x: 530, y: 252 } });
  const eIntake = new Edge({ points: [[895, 270], [895, rowY]], color: C });
  const eOpen = new Edge({ points: [[760, 460], [640, 460]], color: C, label: { text: L.edges.open, x: 700, y: 436 } });
  const eStart = new Edge({ points: [[790, 530], [790, 585]], color: C, label: { text: L.edges.start, x: 808, y: 560, align: 'left' } });
  const eSteer = new Edge({
    points: [[440, 530], [440, 585]], color: C, both: true,
    label: { text: L.edges.steer, x: 422, y: 558, align: 'right' },
  });
  const eWatch = new Edge({
    points: [[390, 270], [390, rowY]], color: H, both: true,
    label: { text: L.edges.watch, x: 408, y: 340, align: 'left' },
  });
  const eCall = new Edge({ points: [[540, 805], [540, 865]], color: C, label: { text: L.edges.call, x: 558, y: 835, align: 'left' } });
  const eModels = new Edge({ points: [[470, 995], [470, 1018], [200, 1018], [200, 1040]], color: C });
  const eTools = new Edge({ points: [[540, 995], [540, 1040]], color: C });
  const eToken = new Edge({ points: [[610, 995], [610, 1018], [880, 1018], [880, 1040]], color: C });
  const ePR = new Edge({
    points: [[820, 730], [1060, 730], [1060, 200], [1030, 200]], color: C,
    label: { text: L.edges.pr, x: 940, y: 708 },
  });

  const readyTag = new Pill({ x: 840, y: 122, text: L.readyLabel, color: H });

  const diagram = [
    cluster, developer, github, planner, room, factory, run, gateway, upstream,
    eAsk, ePlan, eFile, eReview, eIntake, eOpen, eStart, eSteer, eWatch, eCall, eModels, eTools, eToken, ePR,
    readyTag,
  ];
  for (const e of diagram) scene.add(e, 'diagram');

  const title = scene.add(
    new TitleCard({
      logo: assets.logo,
      logoAspect: assets.logoAspect,
      title: T.text,
      subtitle: T.subtitle,
      kicker: T.kicker,
      headerRight: T.url,
      accent: C,
    }),
  );
  const caption = scene.add(new Caption({ y: 1243 }));
  // the first caption runs to three lines; nothing sits below the cluster yet, so it rises
  const captionHigh = scene.add(new Caption({ y: 1200 }));
  const footer = scene.add(new Text({ x: 540, y: 1335, text: `${T.url} · ${T.licence}`, size: 20, color: theme.faint, weight: 500 }));

  // ---- beat 1 · hook ---------------------------------------------------------
  const h = beats.hook;
  title.dockAt(h.end - 1.6, 1.1);
  grid.to(1, h.end - 1.2, 1.0);

  // ---- beat 2 · ask ----------------------------------------------------------
  const b1 = beats.ask;
  const t1 = (dt: number) => b1.start + dt;
  captionHigh.cue(b1.caption!, b1.start, b1.end - 0.2);

  cluster.show(t1(0), 1.2);
  developer.show(t1(0.2));
  eAsk.drawIn(t1(0.6), 0.4).packet(t1(0.9), 0.8, 'sentence', H);
  planner.show(t1(0.8)).highlight(t1(1.7)).pulse(t1(1.8));
  ePlan.drawIn(t1(2.0), 0.4).packet(t1(2.3), 0.8, 'plan');
  developer.highlight(t1(3.0));
  planner.unhighlight(t1(3.2));
  eFile.drawIn(t1(3.2), 0.5).packet(t1(3.5), 0.9, 'issue', H);
  github.show(t1(3.4)).pulse(t1(4.3));
  readyTag.show(t1(4.3));
  eFile.flowOn(t1(4.0));

  // ---- beat 3 · intake -------------------------------------------------------
  const b2 = beats.intake;
  const t2 = (dt: number) => b2.start + dt;
  caption.cue(b2.caption!, b2.start, b2.end - 0.2);

  developer.unhighlight(t2(0));
  for (const e of [planner, eAsk, ePlan]) e.dimAt(t2(0.2));
  eIntake.drawIn(t2(0.1), 0.35).packet(t2(0.2), 0.6);
  factory.show(t2(0.3)).highlight(t2(0.5));
  eStart.drawIn(t2(0.9), 0.45);
  run.show(t2(1.1)).highlight(t2(1.3)).revealInner(t2(1.5));
  factory.unhighlight(t2(1.4));
  eFile.flowOff(t2(1.0));
  // the intake path is done: dim it
  for (const e of [github, readyTag, eFile, eIntake]) e.dimAt(t2(1.8));
  eOpen.drawIn(t2(2.0), 0.5);
  room.show(t2(2.3));
  eSteer.drawIn(t2(2.8), 0.5).flowOn(t2(3.3));
  eWatch.drawIn(t2(3.2), 0.35).flowOn(t2(3.6));
  room.highlight(t2(3.4));
  developer.highlight(t2(3.7));

  // ---- beat 4 · identity -----------------------------------------------------
  const b3 = beats.identity;
  const t3 = (dt: number) => b3.start + dt;
  caption.cue(b3.caption!, b3.start, b3.end - 0.2);
  for (const e of [room, developer, eSteer, eWatch, eOpen, eStart]) e.dimAt(t3(0.2));
  room.unhighlight(t3(0));
  developer.unhighlight(t3(0));
  eSteer.flowOff(t3(0));
  eWatch.flowOff(t3(0));
  run.highlight(t3(0.2));
  eCall.drawIn(t3(0.3), 0.45).flowOn(t3(0.8));
  gateway.show(t3(0.6)).highlight(t3(0.8)).pulse(t3(0.9));
  upstream.show(t3(1.4)).revealSegments(t3(1.5), 0.3);
  eModels.drawIn(t3(1.6), 0.45);
  eTools.drawIn(t3(1.85), 0.35);
  eToken.drawIn(t3(2.1), 0.45);
  // one call per upstream, in turn
  eCall.packet(t3(2.5), 0.45);
  eModels.packet(t3(2.85), 0.6);
  upstream.segHighlight(0, t3(3.4), 0.6);
  eCall.packet(t3(3.5), 0.45);
  eTools.packet(t3(3.85), 0.45);
  upstream.segHighlight(1, t3(4.25), 0.6);
  eCall.packet(t3(4.35), 0.45);
  eToken.packet(t3(4.7), 0.6, undefined, theme.text);
  upstream.segHighlight(2, t3(5.25), 0.6);

  // ---- beat 5 · pull request -------------------------------------------------
  const b4 = beats.pr;
  const t4 = (dt: number) => b4.start + dt;
  caption.cue(b4.caption!, b4.start, b4.end - 0.2);
  for (const e of [gateway, upstream, eCall, eModels, eTools, eToken]) e.dimAt(t4(0.2));
  gateway.unhighlight(t4(0));
  eCall.flowOff(t4(0));
  for (const e of [github, readyTag, eFile, eIntake]) e.undimAt(t4(0.4));
  readyTag.hide(t4(0.4));
  ePR.drawIn(t4(0.3), 1.1).packet(t4(1.5), 1.2, 'PR');
  github.highlight(t4(2.6)).pulse(t4(2.7));
  run.unhighlight(t4(2.6));
  eReview.drawIn(t4(3.0), 0.5).packet(t4(3.6), 0.9, 'review', H);
  developer.undimAt(t4(3.0)).highlight(t4(3.4));
  eWatch.undimAt(t4(3.0));

  // ---- beat 6 · outro --------------------------------------------------------
  const b6 = beats.outro;
  const t6 = (dt: number) => b6.start + dt;
  caption.cue(b6.caption!, b6.start + 0.6, b6.end - 1.3);
  for (const e of diagram) e.undimAt(t6(0.2), 0.6);
  for (const n of [github, developer, run]) n.unhighlight(t6(0.2));
  ePR.flowOn(t6(0.6));
  eCall.flowOn(t6(0.6));
  eSteer.flowOn(t6(0.6));
  eWatch.flowOn(t6(0.6));
  footer.show(t6(0.8));
  // crossfade back to the hook so the clip loops
  const fade = b6.end - 1.15;
  scene.group('diagram').to(0, fade, 0.9);
  footer.hide(fade, 0.5);
  grid.to(0, fade, 0.9);
  title.undockAt(fade + 0.1, 1.0);

  return scene;
}
