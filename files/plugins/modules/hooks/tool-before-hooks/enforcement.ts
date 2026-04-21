import type { PluginDeps } from "../../deps";
import { dagStatePath, readState } from "../../../state-io";
import { isExempt } from "../../../constants";
import { isOptional, getToolName, allRemainingOptional, isTaskSubagent, getTaskSubagentName, enforcementItemMatches } from "../../dag_engine/enforcement-utils";

/**
 * Generic enforcement handler — runs FIRST in the before-hook pipeline.
 * Blocks tools that aren't the currently expected enforcement item.
 * Supports "optional:" prefixed items which can be called or skipped.
 */
export async function handleEnforcementBefore(
  input: any,
  output: any,
  deps: PluginDeps,
): Promise<boolean> {
  if (isExempt(input.tool)) return false;

  const worktree = deps.resolveWorktree(deps.pluginCtx);
  const statePath = dagStatePath(worktree, input.sessionID);
  const state = readState(statePath);

  if (!state) return false;
  if (state.status === "complete" || state.status === "abandoned") return false;

  const node = state.node_map[state.current_node];
  if (!node || node.enforcement.length === 0) return false;

  if (state.status === "waiting_step") {
    // In waiting_step, only allow calling optional items still pending at todo_index.
    // Any other non-exempt tool should be blocked.
    const pendingItem = node.enforcement[state.todo_index];
    if (
      pendingItem &&
      isOptional(pendingItem) &&
      enforcementItemMatches(pendingItem, input.tool, output.args?.subagent_type)
    ) {
      return false; // allow calling the optional item
    }
    throw new Error(
      `[DAG BLOCKED] All required calls for node "${state.current_node}" are complete.\n` +
        `Call next_step to advance to the next node.`,
    );
  }

  // status === "running"
  const currentItem = node.enforcement[state.todo_index];
  if (!currentItem) return false;

  const currentToolName = getToolName(currentItem);

  // Direct match at current position (optional or mandatory).
  // For task:<subagent> items, also validates the subagent_type parameter.
  if (enforcementItemMatches(currentItem, input.tool, output.args?.subagent_type)) {
    // If the tool name matches but subagent_type is wrong, give a targeted error.
    if (isTaskSubagent(currentItem) && input.tool === "task") {
      const expected = getTaskSubagentName(currentItem);
      const actual = output.args?.subagent_type as string | undefined;
      if (actual !== expected) {
        throw new Error(
          `[DAG BLOCKED] task called with subagent_type="${actual ?? "(none)"}" — ` +
            `expected subagent_type="${expected}" for node "${state.current_node}".`,
        );
      }
    }
    return false;
  }

  // task tool called but subagent_type doesn't match the current task:<subagent> item.
  if (isTaskSubagent(currentItem) && input.tool === "task") {
    const expected = getTaskSubagentName(currentItem);
    const actual = output.args?.subagent_type as string | undefined;
    throw new Error(
      `[DAG BLOCKED] task called with subagent_type="${actual ?? "(none)"}" — ` +
        `expected subagent_type="${expected}" for node "${state.current_node}".`,
    );
  }

  if (isOptional(currentItem)) {
    // Current item is optional and the called tool isn't it — find the next mandatory item.
    let nextMandatoryIdx = state.todo_index + 1;
    while (
      nextMandatoryIdx < node.enforcement.length &&
      isOptional(node.enforcement[nextMandatoryIdx])
    ) {
      nextMandatoryIdx++;
    }

    if (nextMandatoryIdx >= node.enforcement.length) {
      // All remaining are optional — nothing mandatory left to call.
      // next_step handles this via allRemainingOptional check; non-exempt others are blocked.
      throw new Error(
        `[DAG BLOCKED] All required calls for node "${state.current_node}" are complete.\n` +
          `Call next_step to advance to the next node.`,
      );
    }

    const nextMandatoryItem = node.enforcement[nextMandatoryIdx];
    if (enforcementItemMatches(nextMandatoryItem, input.tool, output.args?.subagent_type)) return false; // skipping the optional item
  }

  throw new Error(
    `[DAG BLOCKED] Cannot call ${input.tool} — prerequisite not met.\n` +
      `Call ${currentToolName} first to continue.`,
  );
}
