/*
 * A port of crumb_llm/score.py to the browser, and the demo page's only logic.
 *
 * This repository has already paid once for the same idea: three projects each
 * carried a private copy of the CRUMB grammar, nothing compared them, and they
 * drifted until one shipped `v=1.3` against a `v=1.4` spec. A second scorer
 * written for a demo page is exactly that mistake again, so this file is not a
 * fork kept "faithful" by a promise in a comment:
 *
 *   - it lives in the repository, not inside the published page;
 *   - the page loads THIS file rather than an inlined copy;
 *   - tests/test_web_parity.py runs it under node and asserts, score by score
 *     and signal by signal, that it agrees with the Python implementation on
 *     every CRUMB the repository ships.
 *
 * If you change a rule in score.py, change it here, and the parity test will
 * tell you if you didn't.
 *
 * Exported for node as module.exports; also attaches window.CrumbScore.
 */

const WEIGHTS = {
  goal_stated: [2, "a [goal] section states what outcome is wanted"],
  context_anchored: [3, "[context] cites at least one concrete artifact"],
  constraints_declared: [2, "[constraints] lists at least one real bound"],
  next_step_actionable: [3, "[handoff] carries at least one do= directive"],
  ownership_assigned: [1, "every do= directive names a to= owner"],
  verification_defined: [3, "there is a stated way to tell the work worked"],
  progress_recorded: [1, "at least one completed step is marked [x]"],
  references_resolvable: [2, "cited paths are grounded or declared as new"],
};

const TOTAL_WEIGHT = Object.values(WEIGHTS).reduce((a, [w]) => a + w, 0);

const BANDS = [
  [0.35, "unusable", "the next agent would have to reconstruct the task from scratch"],
  [0.60, "thin", "enough to start, not enough to finish without asking questions"],
  [0.85, "usable", "a competent next agent can continue unattended"],
  [1.01, "strong", "goal, grounding, bounds, owner and verification are all present"],
];

const MIN_GOAL_CHARS = 20;

const PATH_RE = /(?:\.{0,2}\/)?(?:[\w.\-]+\/)+[\w.\-]+\.[A-Za-z0-9]{1,8}/g;
const SHA_RE = /\b(?:[0-9a-f]{7,40}|sha256:[0-9a-f]{16,64})\b/g;
const URL_RE = /https?:\/\/\S+/g;
const TICKET_RE = /\b(?:[A-Z][A-Z0-9]+-\d+|#\d+)\b/g;
const SYMBOL_RE = /\b[A-Za-z_][A-Za-z0-9_]*\(\)/g;

const TO_RE = /\bto=(\S+)/;
const DO_RE = /\bdo=(.+?)\s*$/;
const DONE_RE = /^\s*-?\s*\[[xX]\]\s*(.+)$/;

const VERIFICATION_TERMS = [
  "test", "verify", "verified", "verification", "regression", "assert",
  "acceptance", "benchmark", "reproduce", "confirm", "measure", "prove",
  "must pass", "profiler", "profile",
];

const CREATION_VERBS = [
  "add", "create", "write", "new", "introduce", "generate", "scaffold",
  "implement", "produce",
];

const FORWARD_SECTIONS = ["handoff", "constraints"];
const GROUNDING_SECTIONS = ["context", "goal", "consolidated", "entries", "changes"];

const KIND_VERBS = {
  investigation: ["investigate", "find out", "diagnose", "profile", "reproduce", "why", "confirm"],
  implementation: ["add", "implement", "build", "switch", "migrate", "refactor", "fix", "reduce"],
  review: ["review", "approve", "audit", "check over", "sign off"],
  decision: ["decide", "choose", "evaluate", "compare", "select"],
};

/* --- parsing ------------------------------------------------------------ */

/** Parse CRUMB text. Mirrors crumb_core.parse_crumb's shape, not its strictness:
 *  the page reports problems rather than refusing to render, so a half-typed
 *  document still scores instead of throwing. */
function parseCrumb(text) {
  const lines = String(text || "").split("\n").map((l) => l.replace(/\r$/, ""));
  while (lines.length && !lines[0].trim()) lines.shift();
  while (lines.length && !lines[lines.length - 1].trim()) lines.pop();

  const problems = [];
  if (!lines.length || lines[0] !== "BEGIN CRUMB") problems.push("missing BEGIN CRUMB marker");
  if (!lines.length || lines[lines.length - 1] !== "END CRUMB") problems.push("missing END CRUMB marker");

  const sep = lines.indexOf("---");
  if (sep === -1) problems.push("missing header separator ---");

  const headers = {};
  if (sep > -1) {
    for (const line of lines.slice(1, sep)) {
      if (!line.trim()) continue;
      const at = line.indexOf("=");
      if (at === -1) { problems.push(`invalid header line: ${line}`); continue; }
      headers[line.slice(0, at).trim()] = line.slice(at + 1).trim();
    }
  }

  const sections = {};
  let current = null;
  const body = sep > -1 ? lines.slice(sep + 1, lines.length - 1) : [];
  for (const line of body) {
    const stripped = line.trim();
    if (stripped.startsWith("[") && stripped.endsWith("]")) {
      current = stripped.slice(1, -1).trim().toLowerCase();
      if (!(current in sections)) sections[current] = [];
      continue;
    }
    if (current === null) continue;
    sections[current].push(line);
  }

  return { headers, sections, raw: String(text || ""), problems };
}

function findAll(re, text) {
  const out = [];
  const rx = new RegExp(re.source, re.flags.includes("g") ? re.flags : re.flags + "g");
  let m;
  while ((m = rx.exec(text)) !== null) { out.push(m[0]); if (m.index === rx.lastIndex) rx.lastIndex++; }
  return out;
}

function extractFilePaths(text) {
  const found = new Set();
  for (const raw of findAll(PATH_RE, text || "")) {
    const cleaned = raw.replace(/^[`"'([,\]]+|[`"')\],]+$/g, "");
    if (cleaned) found.add(cleaned);
  }
  return found;
}

function sectionLines(doc, ...names) {
  const out = [];
  for (const name of names) {
    for (const line of doc.sections[name] || []) {
      if (line.trim()) out.push(line.trim());
    }
  }
  return out;
}

function anchors(text) {
  const out = [];
  for (const p of [...extractFilePaths(text)].sort()) out.push(p);
  for (const re of [URL_RE, TICKET_RE, SYMBOL_RE, SHA_RE]) out.push(...findAll(re, text));
  return [...new Set(out)];
}

function directives(doc) {
  const list = [];
  const done = [];
  for (const line of sectionLines(doc, "handoff", "tasks")) {
    if (DONE_RE.test(line)) { done.push(line); continue; }
    const doMatch = line.match(DO_RE);
    if (!doMatch) continue;
    const toMatch = line.match(TO_RE);
    list.push({ to: toMatch ? toMatch[1] : "", do: doMatch[1].trim(), raw: line });
  }
  return { directives: list, done };
}

function truncate(lines, limit = 3) {
  const out = [];
  for (const line of lines) {
    if (out.length >= limit) { out.push("..."); break; }
    out.push(line.length <= 160 ? line : line.slice(0, 157) + "...");
  }
  return out;
}

function bandFor(score) {
  for (const [threshold, name, reason] of BANDS) {
    if (score < threshold) return [name, reason];
  }
  return [BANDS[BANDS.length - 1][1], BANDS[BANDS.length - 1][2]];
}

function signal(id, passed, reason, evidence) {
  const [weight, description] = WEIGHTS[id];
  return { id, passed, weight, description, reason, evidence: evidence || [] };
}

/* --- the rules ---------------------------------------------------------- */

function goalStated(doc) {
  const lines = sectionLines(doc, "goal", "consolidated", "identity");
  const text = lines.join(" ");
  if (!text) return signal("goal_stated", false, "no [goal] section, or it is empty", []);
  if (text.length < MIN_GOAL_CHARS) {
    return signal("goal_stated", false, `[goal] is ${text.length} characters — a title, not an outcome`, truncate(lines));
  }
  return signal("goal_stated", true, `[goal] states an outcome in ${text.length} characters`, truncate(lines));
}

function contextAnchored(doc) {
  const lines = sectionLines(doc, ...GROUNDING_SECTIONS);
  if (!lines.length) return signal("context_anchored", false, "no grounding section present", []);
  const found = anchors(lines.join("\n"));
  if (!found.length) {
    return signal("context_anchored", false, "[context] is prose with no file, symbol, commit, ticket or URL to open", truncate(lines));
  }
  return signal("context_anchored", true, `${found.length} concrete anchor(s) the next agent can open`, truncate(found, 6));
}

function constraintsDeclared(doc) {
  const lines = sectionLines(doc, "constraints");
  if (!lines.length) {
    return signal("constraints_declared", false, "no [constraints] — the next agent does not know what it must not break", []);
  }
  return signal("constraints_declared", true, `${lines.length} constraint line(s) declared`, truncate(lines));
}

function nextStepActionable(doc, dirs) {
  if (!dirs.length) {
    return signal("next_step_actionable", false, "no do= directive in [handoff] — nothing tells the next agent what to do first", truncate(sectionLines(doc, "handoff")));
  }
  return signal("next_step_actionable", true, `${dirs.length} actionable directive(s)`, truncate(dirs.map((d) => d.raw)));
}

function ownershipAssigned(dirs) {
  if (!dirs.length) return signal("ownership_assigned", false, "no directives to assign", []);
  const unowned = dirs.filter((d) => !d.to).map((d) => d.raw);
  if (unowned.length) {
    return signal("ownership_assigned", false, `${unowned.length} of ${dirs.length} directive(s) name no to= owner`, truncate(unowned));
  }
  const owners = [...new Set(dirs.map((d) => d.to))].sort();
  return signal("ownership_assigned", true, `every directive is owned (${owners.join(", ")})`, []);
}

function verificationDefined(doc, dirs) {
  const haystack = sectionLines(doc, ...FORWARD_SECTIONS).filter((l) => !DONE_RE.test(l));
  const hits = [];
  for (const line of haystack) {
    const lowered = line.toLowerCase();
    if (VERIFICATION_TERMS.some((t) => lowered.includes(t))) hits.push(line);
    else if ([...extractFilePaths(line)].some((p) => p.toLowerCase().includes("test"))) hits.push(line);
  }
  if (!hits.length) {
    const ev = dirs.length ? dirs.map((d) => d.raw) : haystack;
    return signal("verification_defined", false, "nothing states how to tell the work succeeded — no test, check or acceptance bound", truncate(ev));
  }
  return signal("verification_defined", true, `${hits.length} line(s) define what 'done' means`, truncate(hits));
}

function progressRecorded(done, doc) {
  if (done.length) {
    return signal("progress_recorded", true, `${done.length} completed step(s) recorded`, truncate(done));
  }
  if ((doc.sections.entries || []).length || (doc.sections.changes || []).length) {
    return signal("progress_recorded", true, "a log or delta section records what already happened", truncate(sectionLines(doc, "entries", "changes")));
  }
  return signal("progress_recorded", false, "no [x] markers and no log — the next agent cannot tell what was already tried", []);
}

function referencesResolvable(doc) {
  const grounded = extractFilePaths(sectionLines(doc, ...GROUNDING_SECTIONS).join("\n"));
  for (const p of extractFilePaths(Object.values(doc.headers).join(" "))) grounded.add(p);
  const groundedBase = new Set([...grounded].map((p) => p.split("/").pop()));

  const dangling = [];
  const declaredNew = [];
  for (const line of sectionLines(doc, ...FORWARD_SECTIONS)) {
    const lowered = line.toLowerCase();
    const creates = CREATION_VERBS.some((v) => new RegExp(`\\b${v}\\w*\\b`).test(lowered));
    for (const path of [...extractFilePaths(line)].sort()) {
      if (grounded.has(path) || groundedBase.has(path.split("/").pop())) continue;
      if (creates) declaredNew.push(`${path} (declared new: ${line})`);
      else dangling.push(`${path} — cited in a next step but never grounded: ${line}`);
    }
  }

  if (dangling.length) {
    return signal("references_resolvable", false, `${dangling.length} path(s) cited as work but grounded nowhere`, truncate(dangling));
  }
  if (declaredNew.length) {
    return signal("references_resolvable", true, `every cited path resolves; ${declaredNew.length} declared as new`, truncate(declaredNew));
  }
  return signal("references_resolvable", true, "every cited path is grounded in context", []);
}

function classifyHandoff(doc, dirs) {
  const text = [sectionLines(doc, "goal").join("\n"), ...dirs.map((d) => d.do)].join(" ").toLowerCase();
  if (!text.trim()) return "unknown";
  const tally = {};
  for (const [kind, verbs] of Object.entries(KIND_VERBS)) {
    tally[kind] = verbs.reduce((a, v) => a + text.split(v).length - 1, 0);
  }
  const best = Object.keys(tally).reduce((a, b) => (tally[b] > tally[a] ? b : a));
  return tally[best] ? best : "unknown";
}

/* --- public ------------------------------------------------------------- */

function scoreText(text) {
  const doc = parseCrumb(text);
  const { directives: dirs, done } = directives(doc);

  const signals = [
    goalStated(doc),
    contextAnchored(doc),
    constraintsDeclared(doc),
    nextStepActionable(doc, dirs),
    ownershipAssigned(dirs),
    verificationDefined(doc, dirs),
    progressRecorded(done, doc),
    referencesResolvable(doc),
  ];

  const earned = signals.filter((s) => s.passed).reduce((a, s) => a + s.weight, 0);
  const score = TOTAL_WEIGHT ? earned / TOTAL_WEIGHT : 0;
  const [band, bandReason] = bandFor(score);
  const blocking = dirs.some((d) => d.to.toLowerCase() === "human");

  const notes = [];
  if (blocking) notes.push("at least one directive is to=human — this handoff cannot complete unattended");

  return {
    score,
    band,
    band_reason: bandReason,
    handoff_kind: classifyHandoff(doc, dirs),
    blocking_on_human: blocking,
    signals,
    notes,
    weight_total: TOTAL_WEIGHT,
    weight_earned: earned,
    problems: doc.problems,
  };
}

const CrumbScore = { scoreText, parseCrumb, WEIGHTS, TOTAL_WEIGHT, BANDS };

if (typeof module !== "undefined" && module.exports) module.exports = CrumbScore;
if (typeof window !== "undefined") window.CrumbScore = CrumbScore;
