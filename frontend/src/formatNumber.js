// frontend/src/formatNumber.js
export const num = (value, digits = 3) =>
  typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('en-US', {maximumFractionDigits: digits, useGrouping: false}).format(value)
    : value;