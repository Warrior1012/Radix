// Explicit, defensible alias map: key = canonical id, values = accepted spellings.
// Only true synonyms / abbreviations — never "related" technologies.
export const SKILL_ALIASES: Record<string, { label: string; aliases: string[] }> = {
  javascript: { label: "JavaScript", aliases: ["js", "javascript", "ecmascript", "es6"] },
  typescript: { label: "TypeScript", aliases: ["ts", "typescript"] },
  postgresql: { label: "PostgreSQL", aliases: ["postgres", "postgresql", "psql", "pgsql"] },
  python: { label: "Python", aliases: ["python", "python3", "py"] },
  nodejs: { label: "Node.js", aliases: ["node", "nodejs", "node.js"] },
  react: { label: "React", aliases: ["react", "reactjs", "react.js"] },
  vue: { label: "Vue", aliases: ["vue", "vuejs", "vue.js"] },
  nextjs: { label: "Next.js", aliases: ["next", "nextjs", "next.js"] },
  kubernetes: { label: "Kubernetes", aliases: ["kubernetes", "k8s"] },
  golang: { label: "Go", aliases: ["go", "golang"] },
  csharp: { label: "C#", aliases: ["c#", "csharp", "c sharp"] },
  cpp: { label: "C++", aliases: ["c++", "cpp"] },
  aws: { label: "AWS", aliases: ["aws", "amazon web services"] },
  gcp: { label: "GCP", aliases: ["gcp", "google cloud", "google cloud platform"] },
  azure: { label: "Azure", aliases: ["azure", "microsoft azure"] },
  ml: { label: "Machine Learning", aliases: ["ml", "machine learning"] },
  ai: { label: "Artificial Intelligence", aliases: ["ai", "artificial intelligence"] },
  nlp: { label: "NLP", aliases: ["nlp", "natural language processing"] },
  sql: { label: "SQL", aliases: ["sql"] },
  mongodb: { label: "MongoDB", aliases: ["mongodb", "mongo"] },
  docker: { label: "Docker", aliases: ["docker"] },
  graphql: { label: "GraphQL", aliases: ["graphql", "gql"] },
  cicd: { label: "CI/CD", aliases: ["ci/cd", "cicd", "ci cd"] },
  html: { label: "HTML", aliases: ["html", "html5"] },
  css: { label: "CSS", aliases: ["css", "css3"] },
  tailwind: { label: "Tailwind CSS", aliases: ["tailwind", "tailwindcss", "tailwind css"] },
  restapi: { label: "REST APIs", aliases: ["rest", "rest api", "rest apis", "restful", "restful api"] },
};

const ALIAS_INDEX = new Map<string, string>();
for (const [id, { aliases }] of Object.entries(SKILL_ALIASES)) {
  for (const a of aliases) ALIAS_INDEX.set(a, id);
}

/** Lowercase, trim, collapse whitespace. Keeps symbols like + # . / that matter (C++, C#, Node.js). */
export function cleanSkill(raw: string): string {
  return raw.toLowerCase().replace(/\s+/g, " ").trim();
}

/** Canonical comparison key for a skill. Exact-match only, never substring. */
export function canonicalKey(raw: string): string {
  const c = cleanSkill(raw);
  if (!c) return "";
  return ALIAS_INDEX.get(c) ?? ALIAS_INDEX.get(c.replace(/\s/g, "")) ?? c;
}

/** Display label for a skill: canonical label for known aliases, else trimmed input. */
export function displaySkill(raw: string): string {
  const key = canonicalKey(raw);
  return SKILL_ALIASES[key]?.label ?? raw.replace(/\s+/g, " ").trim();
}

/** Validate, trim, dedupe (by canonical key), preserving first-seen order. */
export function normalizeSkillList(input: unknown): string[] {
  if (!Array.isArray(input)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of input) {
    if (typeof item !== "string") continue;
    const trimmed = item.trim();
    if (!trimmed || trimmed.length > 60) continue;
    const key = canonicalKey(trimmed);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(displaySkill(trimmed));
  }
  return out;
}

/** Split comma / semicolon / newline separated text into skills. */
export function parseSkillText(text: string): string[] {
  return normalizeSkillList(text.split(/[,;\n]/));
}

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Extract skills from free resume text using whole-token matching only
 * against a vocabulary (alias list + supplied job skills). No substring hits:
 * "Java" will not match inside "JavaScript", "Go" not inside "Google".
 */
export function extractSkillsFromText(text: string, vocabulary: string[] = []): string[] {
  if (!text.trim()) return [];
  const terms = new Set<string>();
  for (const { aliases } of Object.values(SKILL_ALIASES)) {
    // Skip ambiguous 2-letter English-ish words in free text.
    for (const a of aliases) if (!["go", "ai", "ml", "js", "ts", "py", "next", "node", "rest"].includes(a)) terms.add(a);
  }
  for (const v of vocabulary) {
    const c = cleanSkill(v);
    if (c.length >= 2) terms.add(c);
  }
  const lower = text.toLowerCase();
  const found: string[] = [];
  for (const term of terms) {
    const re = new RegExp(`(^|[^a-z0-9+#.])${escapeRe(term)}(?![a-z0-9+#])`, "i");
    if (re.test(lower)) found.push(term);
  }
  return normalizeSkillList(found);
}
