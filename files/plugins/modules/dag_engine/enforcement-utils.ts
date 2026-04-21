/** Returns true if the enforcement item is prefixed with "optional:". */
export function isOptional(item: string): boolean {
  return item.startsWith("optional:");
}

/** Strips the "optional:" prefix to get the bare tool name. */
export function getToolName(item: string): string {
  return item.startsWith("optional:") ? item.slice("optional:".length) : item;
}

/** Returns true if all enforcement items from fromIndex onward are optional. */
export function allRemainingOptional(enforcement: string[], fromIndex: number): boolean {
  return enforcement.slice(fromIndex).every(isOptional);
}

/** Returns true if the enforcement item is a task-subagent constraint ("task:<subagent>" or "optional:task:<subagent>"). */
export function isTaskSubagent(item: string): boolean {
  return getToolName(item).startsWith("task:");
}

/** For a "task:<subagent>" item, returns the expected subagent name. Strips "optional:" prefix first. */
export function getTaskSubagentName(item: string): string {
  return getToolName(item).slice("task:".length);
}

/**
 * Returns true if the given enforcement item matches the tool call.
 * For "task:<subagent>" items, also checks that subagentType matches.
 */
export function enforcementItemMatches(item: string, toolName: string, subagentType?: string): boolean {
  if (isTaskSubagent(item)) {
    return toolName === "task" && subagentType === getTaskSubagentName(item);
  }
  return getToolName(item) === toolName;
}
