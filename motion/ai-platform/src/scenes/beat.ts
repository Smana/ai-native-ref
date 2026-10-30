/** One stretch of a clip: when it runs and what its caption says. Shared by every storyboard. */
export interface Beat {
  start: number;
  end: number;
  caption?: string;
}
