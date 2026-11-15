export interface FuzzyMatch {
  score: number;
  indices: number[];
}

/** Case-insensitive subsequence match with a consecutive-run bonus. */
function subsequence(query: string, text: string): FuzzyMatch | null {
  let cursor = 0;
  let score = 0;
  let run = 0;
  const indices: number[] = [];

  for (let queryIndex = 0; queryIndex < query.length; queryIndex += 1) {
    const char = query[queryIndex];
    let found = -1;
    for (let index = cursor; index < text.length; index += 1) {
      if (text[index] === char) {
        found = index;
        break;
      }
    }
    if (found === -1) return null;
    run = found === cursor ? run + 1 : 0;
    score += 1 + run * 3;
    if (found === 0 || "/-_.".includes(text[found - 1] ?? "")) score += 4;
    indices.push(found);
    cursor = found + 1;
  }

  return { score, indices };
}

/**
 * Fuzzy match a query against a project-relative path. Matches inside the
 * basename win ties against matches spread across the directory prefix.
 */
export function fuzzyMatch(query: string, path: string): FuzzyMatch | null {
  const needle = query.trim().toLowerCase();
  if (!needle) return { score: 0, indices: [] };

  const haystack = path.toLowerCase();
  if (needle.length > haystack.length) return null;

  const baseStart = path.lastIndexOf("/") + 1;
  const base = haystack.slice(baseStart);
  const full = subsequence(needle, haystack);
  const baseMatch = subsequence(needle, base);
  const lengthPenalty = Math.min(8, path.length / 24);

  if (baseMatch) {
    const shifted = baseMatch.indices.map((index) => index + baseStart);
    const baseScore = baseMatch.score + 10 - lengthPenalty;
    if (!full || baseScore >= full.score) {
      return { score: baseScore, indices: shifted };
    }
  }
  if (full) return { score: full.score - lengthPenalty, indices: full.indices };
  return null;
}
