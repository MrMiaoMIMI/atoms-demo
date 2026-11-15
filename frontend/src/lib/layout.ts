/**
 * Layout helpers shared by the sidebar pages.
 *
 * The sidebar occupies 270px when expanded and 56px when collapsed. Pages cap
 * their content width, so a collapsed sidebar would centre the same width in a
 * much wider area and leave visibly larger gutters. Adding the sidebar delta
 * to the cap keeps the left/right whitespace identical in both states.
 */
export const SIDEBAR_WIDTH = 270;
export const SIDEBAR_COLLAPSED_WIDTH = 56;

export function contentMaxWidth(
  collapsed: boolean,
  expandedWidth: number
): number {
  return collapsed
    ? expandedWidth + (SIDEBAR_WIDTH - SIDEBAR_COLLAPSED_WIDTH)
    : expandedWidth;
}
