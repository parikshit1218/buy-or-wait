import React from 'react';

/**
 * Text Link Button per DESIGN.md
 * - Underlined Forest Ink text (text-forest-ink underline underline-offset-4)
 * - 16px Inter weight 500 (text-body-sm font-medium)
 * - No background, no border
 */
export function TextLinkButton({
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
      className={`inline-flex items-center justify-center bg-transparent text-body-sm font-medium text-forest-ink underline underline-offset-4 transition-all duration-200 ease-out hover:text-spruce hover:translate-x-0.5 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer select-none ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export default TextLinkButton;
