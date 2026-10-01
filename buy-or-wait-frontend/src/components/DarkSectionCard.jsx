import React from 'react';

/**
 * Dark Section Card per DESIGN.md
 * - Forest Ink (#163300) background
 * - 28px radius (rounded-largecards / rounded-[28px])
 * - 40px padding (p-8 md:p-10)
 * - Lime Voltage (#9fe870) text for safe/positive headlines
 * - Alarm Red (#cb272f) text for wait/not recommended headlines
 * - Paper (#ffffff) for body copy
 */
export function DarkSectionCard({
  headline,
  statusType = 'safe', // 'safe' (Lime Voltage) | 'danger' (Alarm Red) | 'neutral' (Paper)
  subtitle,
  children,
  className = '',
  ...props
}) {
  const headlineColor =
    statusType === 'safe'
      ? 'text-lime-voltage'
      : statusType === 'danger'
      ? 'text-alarm-red'
      : 'text-paper';

  return (
    <div
      className={`relative rounded-largecards bg-forest-ink p-8 md:p-10 text-paper shadow-xl ${className}`}
      {...props}
    >
      {headline && (
        <div className="mb-6">
          <h2 className={`font-display-wise text-subheading md:text-heading-sm leading-[1.1] ${headlineColor}`}>
            {headline}
          </h2>
          {subtitle && (
            <p className="mt-2 text-body text-linen-mist/80">
              {subtitle}
            </p>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

export default DarkSectionCard;
