// Agent Factory v3: the scoper, the split, the loop policy and the judgement roles.

import { Scene } from '../engine/scene.js';
import { Track } from '../engine/tween.js';
import { Caption, Text, Edge, Node, Pill, Region, background, theme } from '../components/index.js';
import type { Assets } from '../main.js';
import { beats, duration, labels as L } from './agent-factory-v3.storyboard.js';

const C = theme.cyan; // the run
const J = theme.violet; // judgement roles
const H = theme.neutral; // humans and GitHub

// The canvas has no header: the layout is drawn as if there were one, moved up by OFFSET_Y and
// trimmed to CANVAS_H. CAPTION_Y is the caption band's centre, in the same (unshifted) layout space.
const CANVAS_H = 1280;
const OFFSET_Y = -70;
const CAPTION_Y = 1243;

export function agentFactoryV3(assets: Assets): Scene {
  const grid = new Track(0);
  const scene = new Scene({
    width: theme.width,
    height: CANVAS_H,
    fps: theme.fps,
    duration,
    background: background(grid),
    offset: [0, OFFSET_Y],
  });

  // ---- layout ---------------------------------------------------------------
  const cluster = new Region({ x: 14, y: 300, w: 1026, h: 865, label: L.cluster, color: C, icon: 'cluster', labelAlign: 'right' });

  const maintainer = new Node({ x: 30, y: 130, w: 380, h: 140, title: L.maintainer.title, sub: [L.maintainer.sub], color: H, icon: 'person', subSize: 22 });
  const github = new Node({ x: 650, y: 130, w: 380, h: 140, title: L.github.title, sub: [L.github.sub], color: H, icon: 'github' });
  const scoper = new Node({ x: 650, y: 390, w: 380, h: 140, title: L.scoper.title, sub: [L.scoper.sub], color: J, icon: 'scope', subSize: 22 });
  const task = new Node({ x: 30, y: 390, w: 560, h: 140, title: L.task.title, sub: [L.task.sub], color: C, icon: 'checklist', subSize: 26 });
  const parts = new Node({
    x: 30, y: 390, w: 560, h: 140, title: '', color: C, titleSize: 30,
    segments: L.parts.map((p) => ({ title: p, icon: 'branch' as const })),
  });
  const implementer = new Node({
    x: 260, y: 585, w: 560, h: 220, title: L.implementer.title, color: C, icon: 'cube',
    inner: { label: L.implementer.sandbox, lines: [L.implementer.inside] },
  });
  const search = new Node({ x: 850, y: 630, w: 180, h: 130, title: L.search.title, sub: L.search.sub, color: C, icon: 'search', titleSize: 30, subSize: 20 });
  const judge = new Node({ x: 30, y: 865, w: 430, h: 130, title: L.judge.title, sub: [L.judge.sub], color: J, icon: 'scale', subSize: 22 });
  const reviewer = new Node({ x: 520, y: 865, w: 510, h: 130, title: L.reviewer.title, sub: [L.reviewer.sub], color: J, icon: 'eye', subSize: 20 });
  const gate = new Node({ x: 260, y: 1030, w: 540, h: 110, title: L.gate.title, sub: [L.gate.sub], color: C, icon: 'shield', subSize: 22 });

  const eLabel = new Edge({ points: [[410, 175], [650, 175]], color: H, label: { text: L.edges.label, x: 530, y: 150 } });
  const eReview = new Edge({ points: [[410, 230], [650, 230]], color: H, label: { text: L.edges.review, x: 530, y: 252 } });
  const eIntake = new Edge({ points: [[840, 270], [840, 390]], color: C });
  const eScope = new Edge({ points: [[650, 460], [590, 460]], color: J });
  const eQuestion = new Edge({
    points: [[720, 390], [720, 335], [220, 335], [220, 270]], color: J, dashed: true,
    label: { text: L.edges.question, x: 470, y: 360 },
  });
  const eStart = new Edge({
    points: [[560, 530], [560, 550], [760, 550], [760, 585]], color: C,
    label: { text: L.edges.oneAtATime, x: 780, y: 567, align: 'right' },
  });
  const eOpenPR = new Edge({
    points: [[820, 610], [1050, 610], [1050, 240], [1030, 240]], color: C,
    label: { text: L.edges.openPR, x: 955, y: 588 },
  });
  const eSplit = new Edge({ points: [[220, 322], [220, 390]], color: H, dashed: true });
  const eEscalate = new Edge({
    points: [[30, 980], [22, 980], [22, 300], [60, 300], [60, 270]], color: H, dashed: true,
    label: { text: L.edges.escalate, x: 34, y: 1055, align: 'left' },
  });
  const eSearch = new Edge({ points: [[820, 695], [850, 695]], color: C, both: true });
  const eJudge = new Edge({ points: [[300, 805], [300, 865]], color: J, label: { text: L.edges.finished, x: 282, y: 835, align: 'right' } });
  const eNotYet = new Edge({
    points: [[120, 865], [120, 700], [260, 700]], color: J, dashed: true,
    label: { text: L.edges.notYet, x: 136, y: 760, align: 'left' },
  });
  const eMet = new Edge({ points: [[460, 930], [520, 930]], color: J, label: { text: L.edges.met, x: 490, y: 908 } });
  const eToGate = new Edge({ points: [[780, 995], [780, 1030]], color: C });
  const ePR = new Edge({
    points: [[800, 1085], [1066, 1085], [1066, 190], [1030, 190]], color: C,
    label: { text: L.edges.pr, x: 1050, y: 1030, align: 'right' },
  });

  const readyTag = new Pill({ x: 840, y: 122, text: L.readyLabel, color: H });
  const splitTag = new Pill({ x: 220, y: 300, text: L.splitCommand, color: H });
  const checksTag = new Pill({ x: 385, y: 585, text: L.checks, color: C, align: 'left', size: 21 });
  const stallTag = new Pill({ x: 810, y: 805, text: L.stall, color: C, align: 'right', size: 21 });
  const verdictTag = new Pill({ x: 40, y: 1000, text: L.verdicts, color: J, size: 21, align: 'left' });
  const evidenceTag = new Pill({ x: 770, y: 1000, text: L.evidence, color: J, size: 21, align: 'right' });
  const testerTag = new Pill({ x: 30, y: 560, text: L.tester, color: J, tag: 'switch', size: 20, align: 'left' });
  const needsAuthorTag = new Pill({ x: 840, y: 122, text: L.needsAuthor, color: H, size: 21 });

  const diagram = [
    cluster, maintainer, github, scoper, task, parts, implementer, search, judge, reviewer, gate,
    eLabel, eReview, eIntake, eScope, eQuestion, eStart, eOpenPR, eSplit, eEscalate, eSearch, eJudge, eNotYet, eMet, eToGate, ePR,
    readyTag, splitTag, checksTag, stallTag, verdictTag, evidenceTag, testerTag, needsAuthorTag,
  ];
  for (const e of diagram) scene.add(e, 'diagram');

  const caption = scene.add(new Caption({ y: CAPTION_Y, size: 36, maxWidth: 1000 }));
  // the per-class legend: which class runs which stage, inside the cluster under the gate
  const legend = new Text({ x: 527, y: 1154, text: L.legend, size: 18, family: 'sans', color: theme.muted });
  scene.add(legend, 'diagram');

  grid.to(1, 0, 0.8);

  // ---- beat 2 · scoper -------------------------------------------------------
  const b2 = beats.scoper;
  const t2 = (dt: number) => b2.start + dt;
  caption.cue(b2.caption!, b2.start, b2.end - 0.2, J);
  cluster.show(t2(0), 1.2);
  maintainer.show(t2(0.2));
  eLabel.drawIn(t2(0.6), 0.5).packet(t2(0.9), 0.9, L.readyLabel, H);
  github.show(t2(1.0)).pulse(t2(1.75));
  readyTag.show(t2(1.75));
  eIntake.drawIn(t2(2.0), 0.4).packet(t2(2.1), 0.6);
  scoper.show(t2(2.4)).highlight(t2(2.6)).pulse(t2(2.7));
  eScope.drawIn(t2(3.4), 0.4);
  task.show(t2(3.7)).highlight(t2(3.9));
  // the other answer: a question back to the author
  eQuestion.drawIn(t2(4.8), 0.9).packet(t2(5.3), 1.0, '?', J);
  task.dimAt(t2(4.8));
  readyTag.hide(t2(5.2), 0.2);
  needsAuthorTag.show(t2(5.4));
  maintainer.highlight(t2(6.1)).pulse(t2(6.2));
  for (const e of [github, readyTag, eLabel, eIntake]) e.dimAt(t2(4.0));

  // ---- beat 3 · split --------------------------------------------------------
  const b3 = beats.split;
  const t3 = (dt: number) => b3.start + dt;
  caption.cue(b3.caption!, b3.start, b3.end - 0.2, C);
  maintainer.unhighlight(t3(0));
  task.undimAt(t3(0));
  needsAuthorTag.hide(t3(0.3), 0.3);
  scoper.unhighlight(t3(0));
  for (const e of [eQuestion, scoper, eScope]) e.dimAt(t3(0.3));
  task.hide(t3(0.6), 0.4);
  parts.show(t3(0.7)).revealSegments(t3(0.8), 0.3).highlight(t3(0.9));
  splitTag.show(t3(1.9));
  eSplit.drawIn(t3(2.2), 0.4);
  maintainer.highlight(t3(1.9)).pulse(t3(2.0));
  eStart.drawIn(t3(2.6), 0.6);
  implementer.show(t3(3.0)).revealInner(t3(3.4));
  eStart.packet(t3(3.3), 0.8, L.parts[0]);
  parts.segHighlight(0, t3(3.1), 1.2);
  eStart.packet(t3(4.6), 0.8, L.parts[1]);
  parts.segHighlight(1, t3(4.4), 1.2);
  maintainer.unhighlight(t3(3.0));

  // ---- beat 4 · implementer --------------------------------------------------
  const b4 = beats.implement;
  const t4 = (dt: number) => b4.start + dt;
  caption.cue(b4.caption!, b4.start, b4.end - 0.2, C);
  for (const e of [parts, splitTag, eSplit, maintainer]) e.dimAt(t4(0.3));
  eStart.hide(t4(0.3)); // its label would sit under the checks pill
  parts.unhighlight(t4(0));
  implementer.highlight(t4(0.2)).pulse(t4(0.3));
  eSearch.drawIn(t4(0.9), 0.3).flowOn(t4(1.3));
  search.show(t4(1.1));
  testerTag.show(t4(0.6));
  legend.show(t4(1.0));
  checksTag.show(t4(2.6));
  stallTag.show(t4(4.2));
  eSearch.flowOff(t4(4.0));
  // the implementer opens the pull request; the reviewer runs after it
  eOpenPR.drawIn(t4(5.0), 0.8).packet(t4(5.4), 0.9, 'PR', C);
  github.undimAt(t4(6.0)).pulse(t4(6.1));

  // ---- beat 5 · judge and reviewer -------------------------------------------
  const b5 = beats.judge;
  const b6 = beats.outro;
  const t5 = (dt: number) => b5.start + dt;
  caption.cue(b5.caption!, b5.start, b5.end - 0.2, J);
  for (const e of [search, eSearch, checksTag, stallTag]) e.dimAt(t5(0.3));
  implementer.unhighlight(t5(0.2));
  eJudge.drawIn(t5(0.2), 0.4).packet(t5(0.4), 0.6);
  judge.show(t5(0.6)).highlight(t5(0.8)).pulse(t5(0.9));
  verdictTag.show(t5(1.3));
  eEscalate.drawIn(t5(1.5), 0.8);
  eNotYet.drawIn(t5(1.8), 0.6).packet(t5(2.2), 0.9, L.edges.notYet, J);
  eMet.drawIn(t5(3.2), 0.4).packet(t5(3.4), 0.5, L.edges.met, J);
  reviewer.show(t5(3.7)).highlight(t5(3.9)).pulse(t5(4.0));
  judge.unhighlight(t5(3.9));
  evidenceTag.show(t5(4.6));
  // a human reads the pull request and approves; the gate merges only the low-risk classes
  maintainer.undimAt(t5(4.8));
  eReview.drawIn(t5(5.0), 0.5).packet(t5(5.4), 0.7, 'approve', H);
  eToGate.drawIn(t5(5.6), 0.4);
  gate.show(t5(6.0)).highlight(t5(6.2));
  reviewer.unhighlight(t5(6.0));
  for (const e of [eNotYet, eEscalate]) e.dimAt(t5(3.6));

  // ---- beat 6 · outro --------------------------------------------------------
  const t6 = (dt: number) => b6.start + dt;
  caption.cue(b6.caption!, b6.start + 0.6, b6.end - 1.1, C);
  for (const e of diagram) e.undimAt(t6(0.2), 0.6);
  for (const n of [gate]) n.unhighlight(t6(0.2));
  task.hide(t6(0)); // the parts stay
  for (const e of [github, readyTag]) e.undimAt(t6(0.2));
  ePR.drawIn(t6(0.2), 0.8).flowOn(t6(1.0)).packet(t6(1.0), 1.4, 'merge');
  eJudge.flowOn(t6(0.6));
  eReview.flowOn(t6(0.6));
  github.pulse(t6(2.4));
  maintainer.highlight(t6(2.4));
  // fade to the background so the loop restarts on an empty cluster
  const fade = b6.end - 1.0;
  scene.group('diagram').to(0, fade, 0.8);
  grid.to(0, fade, 0.8);

  return scene;
}
