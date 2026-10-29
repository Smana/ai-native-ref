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
  // Humans and GitHub on the top row, outside the cluster. Everything the
  // factory runs sits inside the Kubernetes region below.
  const col1 = 30;
  const col3 = 650;
  const colW = 380;

  const cluster = new Region({ x: 14, y: 300, w: 1026, h: 715, label: L.cluster, color: C, icon: 'cluster', labelAlign: 'right' });

  const maintainer = new Node({ x: col1, y: 130, w: colW, h: 140, title: L.maintainer.title, sub: [L.maintainer.sub], color: H, icon: 'person' });
  const github = new Node({ x: col3, y: 130, w: colW, h: 140, title: L.github.title, sub: [L.github.sub], color: H, icon: 'github' });
  const room = new Node({ x: col1, y: 390, w: colW, h: 140, title: L.room.title, sub: [L.room.sub], color: C, icon: 'eye' });
  const factory = new Node({ x: col3, y: 390, w: colW, h: 140, title: L.factory.title, sub: [L.factory.sub], color: C, icon: 'factory' });
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

  const eLabel = new Edge({ points: [[410, 175], [650, 175]], color: H, label: { text: L.edges.label, x: 530, y: 150 } });
  const eReview = new Edge({ points: [[410, 230], [650, 230]], color: H, label: { text: L.edges.review, x: 530, y: 252 } });
  const eIntake = new Edge({ points: [[720, 270], [720, 390]], color: C });
  const eOpen = new Edge({ points: [[650, 460], [410, 460]], color: C, label: { text: L.edges.open, x: 530, y: 436 } });
  const eStart = new Edge({ points: [[760, 530], [740, 585]], color: C, label: { text: L.edges.start, x: 775, y: 562, align: 'left' } });
  const eSteer = new Edge({
    points: [[220, 530], [220, 740], [260, 740]], color: C, both: true,
    label: { text: L.edges.steer, x: 204, y: 625, align: 'right' },
  });
  const eWatch = new Edge({
    points: [[220, 270], [220, 390]], color: H, both: true,
    label: { text: L.edges.watch, x: 238, y: 362, align: 'left' },
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
    cluster, maintainer, github, room, factory, run, gateway, upstream,
    eLabel, eReview, eIntake, eOpen, eStart, eSteer, eWatch, eCall, eModels, eTools, eToken, ePR,
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
  const footer = scene.add(new Text({ x: 540, y: 1335, text: `${T.url} · ${T.licence}`, size: 20, color: theme.faint, weight: 500 }));

  // ---- beat 1 · hook ---------------------------------------------------------
  const h = beats.hook;
  title.dockAt(h.end - 1.6, 1.1);
  grid.to(1, h.end - 1.2, 1.0);

  // ---- beat 2 · intake -------------------------------------------------------
  const b2 = beats.intake;
  const t2 = (dt: number) => b2.start + dt;
  caption.cue(b2.caption!, b2.start, b2.end - 0.2);

  cluster.show(t2(0), 1.2);
  maintainer.show(t2(0.2));
  eLabel.drawIn(t2(0.7), 0.5).packet(t2(1.0), 1.0, L.readyLabel, H);
  github.show(t2(1.2)).pulse(t2(1.95));
  readyTag.show(t2(1.95));
  eIntake.drawIn(t2(2.2), 0.35).packet(t2(2.3), 0.6);
  factory.show(t2(2.5)).highlight(t2(2.7));

  eStart.drawIn(t2(3.1), 0.45);
  run.show(t2(3.3)).highlight(t2(3.5)).revealInner(t2(3.7));
  factory.unhighlight(t2(3.6));
  eOpen.drawIn(t2(4.2), 0.5);
  room.show(t2(4.5));
  eSteer.drawIn(t2(5.0), 0.6).flowOn(t2(5.6));
  eWatch.drawIn(t2(5.5), 0.35).flowOn(t2(5.9));
  room.highlight(t2(5.6));
  maintainer.highlight(t2(5.9));
  eLabel.flowOn(t2(3.0)).flowOff(t2(5.0));
  // the intake path is done: dim it
  for (const e of [github, readyTag, eLabel, eIntake]) e.dimAt(t2(4.0));

  // ---- beat 3 · identity -----------------------------------------------------
  const b3 = beats.identity;
  const t3 = (dt: number) => b3.start + dt;
  caption.cue(b3.caption!, b3.start, b3.end - 0.2);
  for (const e of [room, maintainer, eSteer, eWatch, eOpen, eStart]) e.dimAt(t3(0.2));
  room.unhighlight(t3(0));
  maintainer.unhighlight(t3(0));
  eSteer.flowOff(t3(0));
  eWatch.flowOff(t3(0));
  run.highlight(t3(0.2));
  eCall.drawIn(t3(0.3), 0.45).flowOn(t3(0.9));
  gateway.show(t3(0.7)).highlight(t3(0.9)).pulse(t3(1.0));
  upstream.show(t3(1.6)).revealSegments(t3(1.7), 0.35);
  eModels.drawIn(t3(1.8), 0.5);
  eTools.drawIn(t3(2.1), 0.4);
  eToken.drawIn(t3(2.4), 0.5);
  // one call per upstream, in turn
  eCall.packet(t3(2.9), 0.5);
  eModels.packet(t3(3.3), 0.7);
  upstream.segHighlight(0, t3(3.9), 0.7);
  eCall.packet(t3(4.1), 0.5);
  eTools.packet(t3(4.5), 0.5);
  upstream.segHighlight(1, t3(4.9), 0.7);
  eCall.packet(t3(5.1), 0.5);
  eToken.packet(t3(5.5), 0.7, undefined, theme.text);
  upstream.segHighlight(2, t3(6.1), 0.9);

  // ---- beat 4 · pull request -------------------------------------------------
  const b4 = beats.pr;
  const t4 = (dt: number) => b4.start + dt;
  caption.cue(b4.caption!, b4.start, b4.end - 0.2);
  for (const e of [gateway, upstream, eCall, eModels, eTools, eToken]) e.dimAt(t4(0.2));
  gateway.unhighlight(t4(0));
  eCall.flowOff(t4(0));
  for (const e of [github, readyTag, eLabel, eIntake]) e.undimAt(t4(0.4));
  readyTag.hide(t4(0.4));
  ePR.drawIn(t4(0.3), 1.1).packet(t4(1.5), 1.2, 'PR');
  github.highlight(t4(2.6)).pulse(t4(2.7));
  run.unhighlight(t4(2.6));
  eReview.drawIn(t4(3.0), 0.5).packet(t4(3.6), 0.9, 'review', H);
  maintainer.undimAt(t4(3.0)).highlight(t4(3.4));
  eWatch.undimAt(t4(3.0));

  // ---- beat 6 · outro --------------------------------------------------------
  const b6 = beats.outro;
  const t6 = (dt: number) => b6.start + dt;
  caption.cue(b6.caption!, b6.start + 0.6, b6.end - 1.3);
  for (const e of diagram) e.undimAt(t6(0.2), 0.6);
  for (const n of [github, maintainer, run]) n.unhighlight(t6(0.2));
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
