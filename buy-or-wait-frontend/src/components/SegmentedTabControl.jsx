import React from 'react';

/**
 * Segmented Tab Control per DESIGN.md
 * - Pill container with 4px inner padding (p-[4px]), Fog (#e8ebe6) background, 9999px radius
 * - Tabs at 40px height, 9999px radius, 16px Inter 500 text
 * - Active tab: Lime Voltage (#9fe870) fill with Forest Ink (#163300) text
 * - Inactive tabs: transparent with Charcoal (#454745) text, hovering to Forest Ink
 * - Fits inside 72px header with breathing room
 */
export function SegmentedTabControl({
  tabs = [],
  activeTab,
  onChange,
  className = '',
}) {
  return (
    <div
      role="tablist"
      className={`inline-flex items-center rounded-full bg-fog p-[4px] shadow-subtle ${className}`}
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={`inline-flex h-[40px] items-center justify-center rounded-full px-5 text-[16px] font-inter transition-all duration-300 ease-out cursor-pointer select-none active:scale-95 ${
              isActive
                ? 'bg-lime-voltage text-forest-ink shadow-[0_2px_8px_rgba(22,51,0,0.1)] font-semibold scale-[1.01]'
                : 'bg-transparent text-charcoal hover:text-forest-ink hover:bg-paper/40 font-medium'
            }`}
          >
            {tab.icon && <span className="mr-2 inline-block transition-transform duration-200">{tab.icon}</span>}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

export default SegmentedTabControl;
