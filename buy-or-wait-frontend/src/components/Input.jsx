import React from 'react';

/**
 * Standard Input Field per DESIGN.md
 * - 10px radius (rounded-inputs / rounded-[10px])
 * - 1px Pebble (#868685) border (border border-pebble)
 * - 12px vertical, 16px horizontal padding (py-3 px-4)
 * - Inter 400 at 16px (text-body-sm font-normal text-charcoal placeholder:text-pebble)
 * - Focus state: Forest Ink (#163300) border, no glow ring (focus:border-forest-ink focus:outline-none)
 */
export function Input({
  value,
  onChange,
  placeholder = '',
  type = 'text',
  disabled = false,
  className = '',
  id,
  name,
  ...props
}) {
  return (
    <input
      type={type}
      id={id}
      name={name}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
      className={`w-full rounded-inputs border border-pebble bg-paper px-4 py-3 text-body-sm font-normal text-charcoal placeholder:text-pebble transition-colors focus:border-forest-ink focus:outline-none disabled:bg-fog disabled:cursor-not-allowed ${className}`}
      {...props}
    />
  );
}

export default Input;
