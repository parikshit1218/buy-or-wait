import React from 'react';
import {
  ShieldCheck,
  CalendarClock,
  Banknote,
  AlertTriangle,
  Clock,
  Layers,
  ArrowUpRight,
  Lock,
  Wallet,
  CheckCircle,
} from 'lucide-react';

/**
 * Icon resolver mapping factor types or icon names to 24px Charcoal stroke icons
 */
export function getFactorIcon(iconType) {
  const props = { className: 'h-6 w-6 stroke-charcoal stroke-[1.75]' };

  switch (iconType) {
    case 'shield':
    case 'reserve':
    case 'buffer':
      return <ShieldCheck {...props} />;
    case 'calendar':
    case 'date':
    case 'horizon':
      return <CalendarClock {...props} />;
    case 'cash':
    case 'payment':
    case 'money':
      return <Banknote {...props} />;
    case 'installments':
    case 'plan':
      return <Layers {...props} />;
    case 'alert':
    case 'warning':
      return <AlertTriangle {...props} />;
    case 'lock':
    case 'essential':
      return <Lock {...props} />;
    case 'recovery':
    case 'income':
      return <ArrowUpRight {...props} />;
    case 'wallet':
      return <Wallet {...props} />;
    default:
      return <CheckCircle {...props} />;
  }
}

/**
 * Feature Row per DESIGN.md
 * - Three-column trust signal block — icon + heading + supporting line
 * - Single-column on mobile, three-column on desktop
 * - Icon at 24px stroke #454745
 * - 24px vertical gap between icon and heading (mb-6)
 * - Heading: Inter 700 at 18px in #0e0f0c (font-bold text-[18px] text-obsidian)
 * - 8px vertical gap to body (mb-2)
 * - Body: Inter 400 at 16px Pebble #868685 (font-normal text-[16px] text-pebble leading-relaxed)
 * - Column gap 32px (gap-8), centered max-width 1200px
 */
export function FeatureRow({
  factors = [],
  title = 'Key Decision Factors',
  className = '',
}) {
  if (!factors || factors.length === 0) return null;

  return (
    <section className={`rounded-cards bg-fog p-8 md:p-10 shadow-subtle ${className}`}>
      {title && (
        <h3 className="text-body-lg font-bold text-obsidian mb-8 text-center md:text-left">
          {title}
        </h3>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {factors.map((factor, index) => (
          <div
            key={index}
            className="flex flex-col items-start animate-stagger-fade"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            {/* 24px Icon with Charcoal stroke & 24px vertical gap to heading */}
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-paper border border-fog mb-6 shadow-sm">
              {getFactorIcon(factor.icon)}
            </div>

            {/* Heading: Inter 700 18px text-obsidian with 8px gap */}
            <h4 className="font-bold text-[18px] text-obsidian mb-2 leading-snug">
              {factor.heading}
            </h4>

            {/* One-line explanation: Inter 400 16px Pebble */}
            <p className="font-normal text-[16px] text-pebble leading-relaxed">
              {factor.explanation}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default FeatureRow;
