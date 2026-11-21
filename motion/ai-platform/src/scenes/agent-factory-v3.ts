// The roles clip (Agent Factory v4): a workflow picks the roles, then the merge gate judges the diff.

import { Scene } from '../engine/scene.js';
import { Track } from '../engine/tween.js';
import { Caption, Edge, Node, Pill, Region, background, theme } from '../components/index.js';
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

export function agentFactoryV3(_assets: Assets): Scene {
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
  // Left column: the roles in run order. Right column: what a role asks or calls.
  const cluster = new Region({ x: 14, y: 290, w: 1026, h: 870, label: L.cluster, color: C, icon: 'cluster', labelAlign: 'left' });

  const maintainer = new Node({ x: 30, y: 120, w: 380, h: 130, title: L.maintainer.title, sub: [L.maintainer.sub], color: H, icon: 'person', subSize: 22 });
  const github = new Node({ x: 650, y: 120, w: 380, h: 130, title: L.github.title, sub: [L.github.sub], color: H, icon: 'github', subSize: 24 });
  const workflow = new Node({
    x: 380, y: 340, w: 640, h: 90, title: '', color: C, titleSize: 32,
    segments: L.workflows.map((w) => ({ title: w })),
  });
  const scoper = new Node({ x: 40, y: 460, w: 660, h: 110, title: L.scoper.title, sub: [L.scoper.sub], color: J, icon: 'scope', subSize: 22 });
  const author = new Node({ x: 740, y: 460, w: 280, h: 110, title: L.author.title, sub: [L.author.sub], color: H, icon: 'person', titleSize: 32, subSize: 22 });
  const implementer = new Node({
    x: 40, y: 620, w: 660, h: 200, title: L.implementer.title, color: C, icon: 'cube',
    inner: { label: L.implementer.sandbox, lines: [L.implementer.inside] },
  });
  const search = new Node({ x: 740, y: 620, w: 280, h: 90, title: L.search.title, sub: [L.search.sub], color: C, icon: 'search', titleSize: 30, subSize: 20 });
  const judge = new Node({ x: 740, y: 730, w: 280, h: 90, title: L.judge.title, sub: [L.judge.sub], color: J, icon: 'scale', titleSize: 30, subSize: 20 });
  const reviewer = new Node({ x: 40, y: 870, w: 660, h: 110, title: L.reviewer.title, sub: [L.reviewer.sub], color: J, icon: 'eye', subSize: 22 });
  const gate = new Node({ x: 40, y: 1020, w: 540, h: 110, title: L.gate.title, sub: [L.gate.sub], color: C, icon: 'shield', subSize: 22 });
  const roles = [scoper, author, implementer, search, judge, reviewer, gate];

  const eLabel = new Edge({ points: [[410, 160], [650, 160]], color: H, label: { text: L.edges.label, x: 530, y: 136 } });
  const eReview = new Edge({ points: [[410, 210], [650, 210]], color: H, label: { text: L.edges.review, x: 530, y: 232 } });
  // the selector sits right, under GitHub, and the region label left: a packet never covers the label
  const eIntake = new Edge({ points: [[840, 250], [840, 340]], color: C });
  const eQuestion = new Edge({ points: [[700, 515], [740, 515]], color: J, dashed: true });
  const eTask = new Edge({ points: [[600, 570], [600, 620]], color: J, label: { text: L.edges.task, x: 616, y: 595, align: 'left' } });
  const eSearch = new Edge({ points: [[700, 665], [740, 665]], color: C, both: true });
  const eJudge = new Edge({ points: [[700, 775], [740, 775]], color: J, both: true });
  const eToReviewer = new Edge({ points: [[640, 820], [640, 870]], color: C });
  const eToGate = new Edge({ points: [[500, 980], [500, 1020]], color: C });
  // quick has no reviewer: the implementer's pull request goes straight to the gate
  const eQuick = new Edge({ points: [[40, 760], [24, 760], [24, 1075], [40, 1075]], color: C });
  const ePR = new Edge({
    points: [[900, 1035], [1056, 1035], [1056, 185], [1030, 185]], color: C,
    label: { text: L.edges.pr, x: 1036, y: 950, align: 'right' },
  });

  const readyTag = new Pill({ x: 840, y: 112, text: L.readyLabel, color: H });
  const testerTag = new Pill({ x: 40, y: 595, text: L.tester, color: J, tag: L.testerTag, size: 19, align: 'left' });
  const checksTag = new Pill({ x: 330, y: 820, text: L.checks, color: C, size: 20 });
  const verdictTag = new Pill({ x: 880, y: 845, text: L.verdicts, color: J, size: 20 });
  const liveTag = new Pill({ x: 606, y: 1035, text: L.policies.live, color: C, size: 19, align: 'left' });
  const shadowTag = new Pill({ x: 606, y: 1078, text: L.policies.shadow, color: theme.muted, size: 19, align: 'left', dashed: true });
  const humanTag = new Pill({ x: 606, y: 1121, text: L.policies.human, color: H, size: 19, align: 'left' });

  const diagram = [
    cluster, maintainer, github, workflow, ...roles,
    eLabel, eReview, eIntake, eQuestion, eTask, eSearch, eJudge, eToReviewer, eToGate, eQuick, ePR,
    readyTag, testerTag, checksTag, verdictTag, liveTag, shadowTag, humanTag,
  ];
  for (const e of diagram) scene.add(e, 'diagram');

  const caption = scene.add(new Caption({ y: CAPTION_Y, size: 36, maxWidth: 1000 }));

  /** A role lights up: out of the ghosted state, glowing. */
  const light = (n: Node, at: number) => n.undimAt(at).highlight(at).pulse(at + 0.1);

  grid.to(1, 0, 0.8);

  // ---- beat 1 · intake: a workflow picks the roles ----------------------------
  const b1 = beats.intake;
  const t1 = (dt: number) => b1.start + dt;
  caption.cue(b1.caption!, b1.start, b1.end - 0.2, C);
  cluster.show(t1(0), 1.2);
  maintainer.show(t1(0.2));
  eLabel.drawIn(t1(0.6), 0.5).packet(t1(0.9), 0.9, L.readyLabel, H);
  github.show(t1(1.0)).pulse(t1(1.75));
  readyTag.show(t1(1.75));
  eIntake.drawIn(t1(1.9), 0.5);
  workflow.show(t1(2.2)).revealSegments(t1(2.4), 0.2);
  // every role is there, ghosted: each workflow lights its own
  roles.forEach((n, i) => n.dimAt(t1(0), 0).show(t1(2.8 + i * 0.12)));
  for (const e of [readyTag, eLabel]) e.dimAt(t1(4.2));

  // ---- beat 2 · quick ----------------------------------------------------------
  const b2 = beats.quick;
  const t2 = (dt: number) => b2.start + dt;
  caption.cue(b2.caption!, b2.start, b2.end - 0.2, C);
  eIntake.packet(t2(0.1), 0.8, L.picks[0]);
  workflow.segHighlight(0, t2(0.6), 3.4);
  light(implementer, t2(0.8));
  implementer.revealInner(t2(1.1));
  eQuick.drawIn(t2(2.0), 0.6).packet(t2(2.5), 1.0, 'PR');
  implementer.unhighlight(t2(4.2));
  eQuick.hide(t2(4.2), 0.4);

  // ---- beat 3 · standard -------------------------------------------------------
  const b3 = beats.standard;
  const t3 = (dt: number) => b3.start + dt;
  caption.cue(b3.caption!, b3.start, b3.end - 0.2, J);
  eIntake.packet(t3(0.1), 0.8, L.picks[1]);
  workflow.segHighlight(1, t3(0.5), 4.0);
  implementer.highlight(t3(0.7));
  checksTag.show(t3(1.2));
  eToReviewer.drawIn(t3(2.0), 0.4).packet(t3(2.3), 0.7, 'PR');
  implementer.unhighlight(t3(2.6));
  light(reviewer, t3(2.6));
  reviewer.unhighlight(t3(4.6));

  // ---- beat 4 · careful: the scoper --------------------------------------------
  const b4 = beats.scope;
  const t4 = (dt: number) => b4.start + dt;
  caption.cue(b4.caption!, b4.start, b4.end - 0.2, J);
  eIntake.packet(t4(0.1), 0.8, L.picks[2]);
  workflow.segHighlight(2, t4(0.5), 11.3);
  light(scoper, t4(0.9));
  eQuestion.drawIn(t4(2.0), 0.4).packet(t4(2.3), 0.7, '?', J);
  light(author, t4(2.6));
  author.unhighlight(t4(4.0));
  eTask.drawIn(t4(4.0), 0.4).packet(t4(4.3), 0.7);
  testerTag.show(t4(4.9));
  scoper.unhighlight(t4(5.6));
  implementer.highlight(t4(5.6));

  // ---- beat 5 · careful: search, the judge -------------------------------------
  const b5 = beats.build;
  const t5 = (dt: number) => b5.start + dt;
  caption.cue(b5.caption!, b5.start, b5.end - 0.2, C);
  search.undimAt(t5(0.4));
  eSearch.drawIn(t5(0.4), 0.3).flowOn(t5(0.7)).flowOff(t5(2.2));
  light(judge, t5(2.2));
  eJudge.drawIn(t5(2.2), 0.3).packet(t5(2.5), 0.6, 'done?', J);
  verdictTag.show(t5(3.0));
  judge.unhighlight(t5(4.2));
  implementer.unhighlight(t5(4.2));
  eToReviewer.packet(t5(4.0), 0.7, 'PR');
  reviewer.highlight(t5(4.4));

  // ---- beat 6 · the merge gate --------------------------------------------------
  const b6 = beats.gate;
  const t6 = (dt: number) => b6.start + dt;
  caption.cue(b6.caption!, b6.start + 0.2, b6.end - 1.1, C);
  reviewer.unhighlight(t6(0.2));
  eToGate.drawIn(t6(0.2), 0.4).packet(t6(0.4), 0.6, 'PR');
  light(gate, t6(0.7));
  for (const e of [github, readyTag, eLabel]) e.undimAt(t6(0.4));
  // the gate picks the policy from the diff
  liveTag.show(t6(1.6));
  ePR.drawIn(t6(2.0), 0.8).packet(t6(2.6), 1.2, 'merge');
  github.pulse(t6(3.6));
  shadowTag.show(t6(3.6));
  humanTag.show(t6(4.4));
  maintainer.highlight(t6(4.6)).pulse(t6(4.7));
  eReview.drawIn(t6(4.8), 0.5).packet(t6(5.1), 0.7, 'approve', H);
  ePR.flowOn(t6(5.6));
  // fade to the background so the loop restarts on an empty cluster
  const fade = b6.end - 1.0;
  scene.group('diagram').to(0, fade, 0.8);
  grid.to(0, fade, 0.8);

  return scene;
}
