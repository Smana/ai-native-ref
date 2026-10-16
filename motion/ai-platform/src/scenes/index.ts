import type { Scene } from '../engine/scene.js';
import type { Assets } from '../main.js';
import { agentFactory } from './agent-factory.js';

/** Every clip in this project, by name (`--scene <name>`). */
export const scenes: Record<string, (assets: Assets) => Scene> = {
  'agent-factory': agentFactory,
};
