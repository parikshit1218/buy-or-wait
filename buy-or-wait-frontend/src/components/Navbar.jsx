import React from 'react';
import { SegmentedTabControl } from './SegmentedTabControl';

/**
 * Top Navigation Bar per DESIGN.md
 * - Sticky header bar with fixed 72px height on desktop
 * - Background: Paper (#ffffff), Border bottom: 1px Fog (#e8ebe6)
 * - Left: "BUY OR WAIT?" in Inter Black 900, 20px, Forest Ink with lime dot
 * - Center: Segmented Tab Control in Fog container
 * - Mobile (< 768px): 2 rows (row 1 logo, row 2 centered tabs)
 */
export function Navbar({
  tabs,
  activeTab,
  onTabChange,
}) {
  return (
    <header className="sticky top-0 z-50 bg-paper border-b border-fog shadow-[0_1px_3px_rgba(0,0,0,0.03)]">
      {/* Desktop Layout (md and above): Exact 72px fixed height with logo left and tabs centered */}
      <div className="hidden md:flex relative items-center justify-between h-[72px] px-[32px] py-[12px] w-full max-w-[1400px] mx-auto">
        {/* Logo on Left */}
        <div className="flex items-center gap-2.5 z-10">
          <span className="h-2.5 w-2.5 rounded-full bg-lime-voltage shrink-0 shadow-[0_0_8px_rgba(159,232,112,0.8)]"></span>
          <span className="font-display-wise font-black text-[20px] text-forest-ink tracking-tight uppercase select-none">
            BUY OR WAIT?
          </span>
        </div>

        {/* Segmented Tab Control Truly Centered */}
        <nav className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="pointer-events-auto">
            <SegmentedTabControl
              tabs={tabs}
              activeTab={activeTab}
              onChange={onTabChange}
            />
          </div>
        </nav>

        {/* Empty balanced container on right to maintain symmetry */}
        <div className="w-[140px] z-10 pointer-events-none" />
      </div>

      {/* Mobile Layout (< 768px): 2-Row Stack */}
      <div className="flex md:hidden flex-col w-full bg-paper">
        {/* Row 1: Centered Logo */}
        <div className="flex items-center justify-center h-[52px] px-4">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-lime-voltage shrink-0 shadow-[0_0_6px_rgba(159,232,112,0.8)]"></span>
            <span className="font-display-wise font-black text-[18px] text-forest-ink tracking-tight uppercase">
              BUY OR WAIT?
            </span>
          </div>
        </div>

        {/* Row 2: Tabs Full Width */}
        <div className="w-full pb-3 px-3 flex justify-center border-t border-fog/40">
          <SegmentedTabControl
            tabs={tabs}
            activeTab={activeTab}
            onChange={onTabChange}
            className="w-full max-w-sm justify-center"
          />
        </div>
      </div>
    </header>
  );
}

export default Navbar;

