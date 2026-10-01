import React from 'react';

/**
 * Primary CTA Pill Button per DESIGN.md
 * - Filled Lime Voltage (#9fe870) pill
 * - Charcoal (#454745) / Forest Ink text
 * - 9999px radius (rounded-full)
 * - Inter weight 500 at 16px (text-body-sm font-medium)
 * - Padding 11px vertical, 24px horizontal (py-[11px] px-6)
 * - No border, no shadow
 */
export function PrimaryButton({
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
      className={`inline-flex items-center justify-center rounded-full bg-lime-voltage px-6 py-[11px] text-body-sm font-medium text-forest-ink transition-all duration-200 ease-out hover:scale-[1.02] hover:shadow-md active:scale-[0.98] active:brightness-95 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100 disabled:hover:shadow-none cursor-pointer select-none ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export default PrimaryButton;
