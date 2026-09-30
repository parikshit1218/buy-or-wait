import React, { useState, useEffect } from 'react';
import {
  Navbar,
  HeroSection,
  ScrollRevealSection,
} from './components';
import { MyMoneyPage, DecisionPage } from './pages';

export function App() {
  const [activeTab, setActiveTab] = useState('ask-out-loud');
  const [navigationParams, setNavigationParams] = useState({});

  const tabs = [
    { id: 'ask-out-loud', label: 'Ask Out Loud' },
    { id: 'can-i-buy-this', label: 'Can I Buy This?' },
    { id: 'my-money', label: 'My Money' },
  ];

  // Smooth Scroll to Section when Tab or CTA is Clicked
  const handleScrollTo = (sectionId, params = {}) => {
    setNavigationParams(params);
    setActiveTab(sectionId);
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // ScrollSpy: Update active tab based on window scroll position
  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 220;
      const sections = ['ask-out-loud', 'can-i-buy-this', 'my-money'];

      for (const sectionId of sections) {
        const element = document.getElementById(sectionId);
        if (element) {
          const top = element.offsetTop;
          const height = element.offsetHeight;
          if (scrollPosition >= top && scrollPosition < top + height) {
            setActiveTab(sectionId);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-paper text-charcoal flex flex-col font-sans selection:bg-lime-voltage selection:text-forest-ink">
      {/* Sticky Top Navigation Bar with Segmented Tab Control */}
      <Navbar
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={(tabId) => handleScrollTo(tabId)}
      />

      {/* Main Single-Page Scroll Container */}
      <main className="flex-1 mx-auto w-full max-w-[1200px] px-4 sm:px-6 pt-8 sm:pt-12 md:pt-16 pb-12 space-y-16 md:space-y-24">
        {/* SECTION 1: HERO & VOICE ORB ("Ask Out Loud") */}
        <HeroSection onScrollTo={handleScrollTo} />

        {/* SECTION 2: "Can I Buy This?" (Scroll Reveal) */}
        <ScrollRevealSection id="can-i-buy-this">
          <DecisionPage
            initialParams={navigationParams}
            onNavigate={handleScrollTo}
          />
        </ScrollRevealSection>

        {/* SECTION 3: "My Money" (Scroll Reveal) */}
        <ScrollRevealSection id="my-money">
          <MyMoneyPage onNavigate={handleScrollTo} />
        </ScrollRevealSection>
      </main>

      {/* Footer per DESIGN.md */}
      <footer className="border-t border-fog bg-fog/50 py-10 px-6 text-center text-caption text-slate mt-20">
        <div className="mx-auto max-w-[1200px] flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded-full bg-forest-ink flex items-center justify-center">
              <span className="h-2 w-2 rounded-full bg-lime-voltage"></span>
            </div>
            <span className="font-bold text-forest-ink">
              Wise-Engineered Deterministic Decision Platform
            </span>
          </div>
          <p className="text-micro text-pebble">
            Deep Moss with Lime Voltage · 90-Day Liquidity Forecast Invariants · Indian Rupees (₹)
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
