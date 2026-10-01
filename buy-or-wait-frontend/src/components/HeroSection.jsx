import React from 'react';
import { PrimaryButton, TextLinkButton } from './index';
import { VoiceOrb } from './VoiceOrb';
import { ArrowDown } from 'lucide-react';

/**
 * HeroSection Component
 * - Single unified "Ask Out Loud" voice assistant section
 * - Eyebrow: "VOICE ASSISTANT & INSTANT QUERIES"
 * - Large headline: "ASK OUT LOUD" in Inter Black 900 (61px - 89px scale, tight letter-spacing)
 * - One-line description in Inter 400 body-lg
 * - Dual CTAs ("Check Now" & "How it works")
 * - Central interactive Voice Assistant Orb with chips, input, and transcript history
 */
export function HeroSection({ onScrollTo }) {
  const handleScroll = (sectionId) => {
    if (onScrollTo) {
      onScrollTo(sectionId);
    } else {
      const el = document.getElementById(sectionId);
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section id="ask-out-loud" className="relative pt-6 pb-12 md:pt-10 md:pb-16 text-center max-w-[1100px] mx-auto space-y-16">
      {/* 1. Headline Block */}
      <div className="space-y-4 max-w-4xl mx-auto">
        {/* Eyebrow */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-linen-mist text-forest-ink border border-spruce/10 shadow-sm animate-fadeIn">
          <span className="h-2 w-2 rounded-full bg-lime-voltage animate-pulse" />
          <span className="text-micro sm:text-caption font-bold tracking-wider uppercase">
            Voice Assistant & Instant Queries
          </span>
        </div>

        {/* Large Display Headline (61px - 89px scale, Inter Black 900, tight -0.04em) */}
        <h1 className="font-display-wise font-black text-[44px] sm:text-[64px] md:text-[76px] lg:text-[88px] text-forest-ink leading-[0.95] tracking-[-0.04em] uppercase mx-auto">
          ASK OUT LOUD
        </h1>

        {/* Subheading (Inter 400, Body-LG size, Charcoal) */}
        <p className="mt-3 text-body sm:text-body-lg text-charcoal max-w-2xl mx-auto leading-relaxed font-normal">
          Tap the mic and speak naturally. The AI extracts structured details, runs the deterministic cashflow model, and answers with brutal honesty.
        </p>

        {/* Two CTA Buttons Side by Side */}
        <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-6">
          <PrimaryButton
            onClick={() => handleScroll('can-i-buy-this')}
            className="px-8 py-3.5 text-body-sm sm:text-body w-full sm:w-auto shadow-lg hover:shadow-xl"
          >
            Check Now
          </PrimaryButton>

          <TextLinkButton
            onClick={() => handleScroll('my-money')}
            className="text-body-sm sm:text-body font-semibold text-forest-ink hover:text-spruce inline-flex items-center gap-1.5 py-2"
          >
            <span>How it works</span>
            <ArrowDown className="h-4 w-4" />
          </TextLinkButton>
        </div>
      </div>

      {/* 2. Interactive Voice Assistant Orb, Chips, Input & Transcript Panel */}
      <div className="rounded-largecards bg-fog/40 p-6 sm:p-10 border border-forest-ink/5 shadow-subtle relative overflow-hidden flex items-center justify-center">
        <VoiceOrb />
      </div>
    </section>
  );
}

export default HeroSection;

