import type { ReactNode } from 'react';

/**
 * Shared grid for project cards.
 *
 * The expanded sidebar leaves room for two cards per row, while the collapsed
 * sidebar fits three. Breakpoints are deliberately conservative so cards keep
 * a generous size instead of squeezing as the window narrows: below 1024px the
 * expanded view drops to one column, and the collapsed view only reaches three
 * columns from 1280px up.
 */
export default function CardGrid({
  collapsed,
  children,
  className = '',
}: {
  collapsed: boolean;
  children: ReactNode;
  className?: string;
}) {
  const columns = collapsed
    ? 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'
    : 'grid-cols-1 lg:grid-cols-2';
  return (
    <div className={`grid gap-6 ${columns} ${className}`}>{children}</div>
  );
}
