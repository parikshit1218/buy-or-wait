import React from 'react';

/**
 * Currency Selector Pill Pattern per DESIGN.md
 * Dedicated solely to Indian Rupees (INR / ₹) with Indian formatting.
 */
export function CurrencySelectorPill({
  amount,
  onAmountChange,
  itemName,
  onItemNameChange,
  placeholderItem = 'Item name (e.g. Dell XPS Laptop)',
  placeholderAmount = '45000',
  className = '',
}) {
  return (
    <div
      className={`rounded-cards bg-paper p-4 border border-fog shadow-subtle flex flex-col md:flex-row items-stretch md:items-center gap-4 ${className}`}
    >
      {/* INR Rupee Symbol Badge */}
      <div className="flex items-center gap-3 border-b md:border-b-0 md:border-r border-fog pb-3 md:pb-0 md:pr-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-linen-mist text-forest-ink font-bold text-body-lg shadow-sm">
          ₹
        </div>
        <div>
          <span className="text-caption font-bold text-forest-ink block">INR</span>
          <span className="text-micro text-slate block">Indian Rupee</span>
        </div>
      </div>

      {/* Item Name Input */}
      <div className="flex-1">
        <label className="text-micro font-bold uppercase tracking-wider text-pebble block mb-1">
          Purchase Item
        </label>
        <input
          type="text"
          value={itemName}
          onChange={(e) => onItemNameChange(e.target.value)}
          placeholder={placeholderItem}
          className="w-full bg-transparent text-body-sm font-medium text-charcoal placeholder:text-pebble focus:outline-none"
        />
      </div>

      {/* Amount Input */}
      <div className="w-full md:w-56 border-t md:border-t-0 md:border-l border-fog pt-3 md:pt-0 md:pl-4">
        <label className="text-micro font-bold uppercase tracking-wider text-pebble block mb-1">
          Amount (₹)
        </label>
        <div className="flex items-center gap-1.5">
          <span className="text-body-lg font-bold text-forest-ink">₹</span>
          <input
            type="number"
            min="0"
            step="any"
            value={amount}
            onChange={(e) => onAmountChange(e.target.value)}
            placeholder={placeholderAmount}
            className="w-full bg-transparent text-body-lg font-bold text-charcoal placeholder:text-pebble focus:outline-none"
          />
        </div>
      </div>
    </div>
  );
}

export default CurrencySelectorPill;
