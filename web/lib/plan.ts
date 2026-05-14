import type {
  CanonicalTopic,
  CanonicalEdge,
  TopicEntry,
  TopicState,
  TopicStateMap,
} from "./types";

export interface PlannedTopic {
  topicId: string;
  initialState: "pending" | "mastered";
}

/**
 * The state we treat the topic as for planning, given the user's input.
 *
 * - If the user set an explicit top-level state, use it.
 * - Otherwise, if subtopic states have been customized, infer:
 *     * all subtopics marked the same state → that state
 *     * any other mix → "target" (any subtopic customization implies
 *       the user wants this topic in their plan)
 * - Otherwise, undefined (topic enters the plan only as a prerequisite).
 *
 * Tolerates legacy bare-string entries from earlier shape revisions.
 */
export function effectiveTopicState(
  entry: TopicEntry | TopicState | undefined,
  topic: CanonicalTopic
): TopicState | undefined {
  if (!entry) return undefined;
  if (typeof entry === "string") return entry;
  if (entry.state) return entry.state;

  const customized = entry.subtopics ?? {};
  const customizedKeys = Object.keys(customized);
  if (customizedKeys.length === 0) return undefined;

  const allSubs = topic.subtopics ?? [];
  if (allSubs.length > 0 && allSubs.every((s) => customized[s.slug])) {
    const states = allSubs.map((s) => customized[s.slug]);
    const first = states[0];
    if (states.every((s) => s === first)) return first;
  }
  return "target";
}

/**
 * Build the ordered set of topics for a plan, given per-topic states from the
 * survey. Pure function, no DB or Claude.
 *
 * Targets and their transitive prerequisites form the plan. Topics flagged
 * "known" are still included (for context in the skill tree) but enter the
 * plan in the mastered state so problems are skipped. Targets themselves are
 * never auto-mastered — a "known" target is treated as pending so the user
 * can refresh it.
 */
export function generatePlan(
  topicStates: TopicStateMap,
  allTopics: CanonicalTopic[],
  allEdges: CanonicalEdge[]
): PlannedTopic[] {
  const targetIds: string[] = [];
  const knownIds = new Set<string>();
  for (const t of allTopics) {
    const eff = effectiveTopicState(topicStates[t.id], t);
    if (eff === "target") targetIds.push(t.id);
    else if (eff === "known") knownIds.add(t.id);
  }

  const prereqsOf = new Map<string, Set<string>>();
  for (const t of allTopics) prereqsOf.set(t.id, new Set());
  for (const edge of allEdges) {
    prereqsOf.get(edge.dependent_topic_id)?.add(edge.prerequisite_topic_id);
  }

  const needed = new Set<string>(targetIds);
  const queue = [...targetIds];
  while (queue.length > 0) {
    const id = queue.shift()!;
    for (const prereqId of prereqsOf.get(id) ?? []) {
      if (!needed.has(prereqId)) {
        needed.add(prereqId);
        queue.push(prereqId);
      }
    }
  }

  const adjList = new Map<string, string[]>();
  const inDegree = new Map<string, number>();
  for (const id of needed) {
    adjList.set(id, []);
    inDegree.set(id, 0);
  }
  for (const edge of allEdges) {
    if (needed.has(edge.prerequisite_topic_id) && needed.has(edge.dependent_topic_id)) {
      adjList.get(edge.prerequisite_topic_id)!.push(edge.dependent_topic_id);
      inDegree.set(
        edge.dependent_topic_id,
        (inDegree.get(edge.dependent_topic_id) ?? 0) + 1
      );
    }
  }

  const zeroQueue = [...needed].filter((id) => inDegree.get(id) === 0);
  const sorted: string[] = [];
  while (zeroQueue.length > 0) {
    const id = zeroQueue.shift()!;
    sorted.push(id);
    for (const dep of adjList.get(id) ?? []) {
      const deg = (inDegree.get(dep) ?? 0) - 1;
      inDegree.set(dep, deg);
      if (deg === 0) zeroQueue.push(dep);
    }
  }

  const targetSet = new Set(targetIds);
  return sorted.map((topicId) => ({
    topicId,
    initialState:
      knownIds.has(topicId) && !targetSet.has(topicId) ? "mastered" : "pending",
  }));
}

/**
 * Set of topic IDs that will end up in the plan given the current topic states.
 * Used for the live preview while the user builds their plan in the survey.
 */
export function computePlanMembership(
  topicStates: TopicStateMap,
  allTopics: CanonicalTopic[],
  allEdges: CanonicalEdge[]
): Set<string> {
  const targetIds: string[] = [];
  for (const t of allTopics) {
    if (effectiveTopicState(topicStates[t.id], t) === "target") {
      targetIds.push(t.id);
    }
  }

  const prereqsOf = new Map<string, Set<string>>();
  for (const t of allTopics) prereqsOf.set(t.id, new Set());
  for (const edge of allEdges) {
    prereqsOf.get(edge.dependent_topic_id)?.add(edge.prerequisite_topic_id);
  }

  const needed = new Set<string>(targetIds);
  const queue = [...targetIds];
  while (queue.length > 0) {
    const id = queue.shift()!;
    for (const prereqId of prereqsOf.get(id) ?? []) {
      if (!needed.has(prereqId)) {
        needed.add(prereqId);
        queue.push(prereqId);
      }
    }
  }
  return needed;
}
