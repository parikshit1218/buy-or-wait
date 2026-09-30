import React from 'react';

/**
 * Animated Falling Coins SVG Component
 * - Triggers on verdict card appearance
 * - 5 small coin SVG icons fall from above the card
 * - Bounces once on impact before settling
 * - Pure CSS keyframes completing strictly under 1 second (0.85s)
 */
export function FallingCoins({ count = 5 }) {
  const coins = [
    { id: 1, left: '10%', size: 36, delay: '0s', rotate: '-14deg' },
    { id: 2, left: '26%', size: 32, delay: '0.08s', rotate: '18deg' },
    { id: 3, left: '50%', size: 40, delay: '0.04s', rotate: '-6deg' },
    { id: 4, left: '72%', size: 34, delay: '0.12s', rotate: '22deg' },
    { id: 5, left: '88%', size: 38, delay: '0.06s', rotate: '-16deg' },
  ].slice(0, count);

  return (
    <div className="absolute inset-x-0 -top-8 h-20 pointer-events-none overflow-visible z-20">
      <style>{`
        @keyframes coinFallAndBounce {
          0% {
            transform: translateY(-110px) scale(0.5) rotate(0deg);
            opacity: 0;
          }
          20% {
            opacity: 1;
          }
          62% {
            transform: translateY(24px) scale(1.15, 0.82) rotate(190deg);
          }
          78% {
            transform: translateY(-12px) scale(0.92, 1.08) rotate(270deg);
          }
          92% {
            transform: translateY(24px) scale(1.04, 0.96) rotate(345deg);
          }
          100% {
            transform: translateY(24px) scale(1) rotate(360deg);
            opacity: 1;
          }
        }
        .animate-coin-fall {
          animation: coinFallAndBounce 0.85s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }
      `}</style>

      {coins.map((coin) => (
        <div
          key={coin.id}
          className="absolute animate-coin-fall"
          style={{
            left: coin.left,
            animationDelay: coin.delay,
            transform: `rotate(${coin.rotate})`,
          }}
        >
          <svg
            width={coin.size}
            height={coin.size}
            viewBox="0 0 44 44"
            className="drop-shadow-[0_6px_12px_rgba(0,0,0,0.5)] filter"
          >
            <defs>
              <linearGradient id={`coinRim_${coin.id}`} x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#fff275" />
                <stop offset="40%" stopColor="#ffd700" />
                <stop offset="75%" stopColor="#9fe870" />
                <stop offset="100%" stopColor="#054d28" />
              </linearGradient>
              <radialGradient id={`coinBody_${coin.id}`} cx="35%" cy="30%" r="70%">
                <stop offset="0%" stopColor="#ffffff" />
                <stop offset="25%" stopColor="#fff275" />
                <stop offset="60%" stopColor="#ffd700" />
                <stop offset="90%" stopColor="#c59b27" />
                <stop offset="100%" stopColor="#9fe870" />
              </radialGradient>
            </defs>

            {/* Outer Coin Rim */}
            <circle cx="22" cy="22" r="20" fill={`url(#coinRim_${coin.id})`} stroke="#163300" strokeWidth="2" />
            
            {/* Inner Coin Face */}
            <circle cx="22" cy="22" r="16" fill={`url(#coinBody_${coin.id})`} stroke="#054d28" strokeWidth="1.2" />
            
            {/* Milled Ridge Accents */}
            <circle cx="22" cy="22" r="13" fill="none" stroke="#ffffff" strokeWidth="1" strokeDasharray="2.5 2" opacity="0.8" />

            {/* Indian Rupee Symbol ₹ */}
            <text
              x="22"
              y="29"
              fontSize="19"
              fontWeight="900"
              fontFamily="Inter, sans-serif"
              textAnchor="middle"
              fill="#163300"
              className="select-none font-bold"
            >
              ₹
            </text>
          </svg>
        </div>
      ))}
    </div>
  );
}

export default FallingCoins;
