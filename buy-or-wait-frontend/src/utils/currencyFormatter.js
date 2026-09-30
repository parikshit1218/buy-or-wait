/**
 * Formats numbers into Indian Rupee (₹) format.
 * Example: 218945 -> "₹2,18,945"
 *
 * @param {number|string} val
 * @param {boolean} [includeDecimals=false]
 * @returns {string}
 */
export function formatINR(val, includeDecimals = false) {
  if (val === null || val === undefined || val === '') return '₹0';
  const num = typeof val === 'string' ? parseFloat(val.replace(/,/g, '')) : val;
  if (isNaN(num)) return '₹0';

  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: includeDecimals ? 2 : 0,
    minimumFractionDigits: includeDecimals ? 2 : 0,
  }).format(num);
}

export default formatINR;
