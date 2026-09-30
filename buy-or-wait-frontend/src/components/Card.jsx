import React from 'react';

/**
 * Standard Card component per DESIGN.md
 * - 10px radius (rounded-cards / rounded-[10px])
 * - Fog background (bg-fog)
 * - Standard padding 24px (p-6)
 */
export function Card({
  children,
  className = '',
  ...props
}) {
  return (
    <div
      className={`rounded-cards bg-fog p-6 text-charcoal shadow-subtle ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export default Card;
