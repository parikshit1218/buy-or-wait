import React, { useRef, useEffect, useState } from 'react';

/**
 * ScrollRevealSection Component
 * - Wraps sections and triggers a one-time fade + slide-in animation as it enters the viewport
 * - Uses IntersectionObserver (unsubscribes once triggered)
 */
export function ScrollRevealSection({
  id,
  badge,
  title,
  description,
  children,
  className = '',
}) {
  const sectionRef = useRef(null);
  const [hasRevealed, setHasRevealed] = useState(false);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setHasRevealed(true);
          observer.unobserve(el); // Only reveal once, do not repeat
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      id={id}
      ref={sectionRef}
      className={`scroll-mt-[100px] md:scroll-mt-[88px] transition-all duration-700 ease-out transform ${
        hasRevealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10 pointer-events-none'
      } ${className}`}
    >
      {(badge || title || description) && (
        <div className="mb-8 text-center max-w-2xl mx-auto">
          {badge && (
            <div className="inline-flex items-center gap-2 mb-2 px-3 py-1 rounded-full bg-fog border border-forest-ink/5">
              <span className="h-2 w-2 rounded-full bg-lime-voltage"></span>
              <span className="text-micro font-bold uppercase tracking-wider text-pebble">
                {badge}
              </span>
            </div>
          )}
          {title && (
            <h2 className="font-display-wise text-subheading md:text-heading-sm text-forest-ink leading-[1.05]">
              {title}
            </h2>
          )}
          {description && (
            <p className="mt-3 text-body text-charcoal leading-relaxed">
              {description}
            </p>
          )}
        </div>
      )}

      {children}
    </section>
  );
}

export default ScrollRevealSection;
