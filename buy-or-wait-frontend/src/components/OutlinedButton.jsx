import React from 'react';

/**
 * Outlined Pill Button per DESIGN.md
 * - White fill (bg-paper)
 * - 1px Forest Ink border (border border-forest-ink)
 * - Forest Ink text (text-forest-ink)
 * - 9999px radius (rounded-full)
 * - Inter weight 500 at 16px (text-body-sm font-medium)
 * - Padding 11px vertical, 24px horizontal (py-[11px] px-6)
 */
export function OutlinedButton({
  children,
  onClick,
  type = 'button',
  disabled = false,
  className = '',
  ...props
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-full border border-forest-ink bg-paper px-6 py-[11px] text-body-sm font-medium text-forest-ink transition-all duration-200 ease-out hover:scale-[1.02] hover:bg-fog hover:shadow-sm active:scale-[0.98] active:bg-linen-mist disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100 cursor-pointer select-none ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export default OutlinedButton;
