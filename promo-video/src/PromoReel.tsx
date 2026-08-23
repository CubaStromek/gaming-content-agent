import { AbsoluteFill, Sequence } from "remotion";
import type { PromoReelData } from "./promoReelData";
import { PROMO_REEL_CONFIG } from "./promoReelData";
import { HookFrustrationScene } from "./scenes/promo/HookFrustrationScene";
import { ResetScene } from "./scenes/promo/ResetScene";
import { TerminalRevealScene } from "./scenes/promo/TerminalRevealScene";
import { StoryModeScene } from "./scenes/promo/StoryModeScene";
import { CtaScene } from "./scenes/promo/CtaScene";

const NoiseOverlay: React.FC = () => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      backgroundImage:
        "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.015) 2px, rgba(255,255,255,0.015) 3px)",
      pointerEvents: "none",
      zIndex: 90,
    }}
  />
);

export const PromoReel: React.FC<{ data: PromoReelData }> = ({ data }) => {
  const { scenes } = PROMO_REEL_CONFIG;

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0a" }}>
      <Sequence from={scenes.hook.from} durationInFrames={scenes.hook.duration}>
        <HookFrustrationScene
          line1={data.hookLine1}
          line2={data.hookLine2}
        />
      </Sequence>

      <Sequence from={scenes.reset.from} durationInFrames={scenes.reset.duration}>
        <ResetScene />
      </Sequence>

      <Sequence
        from={scenes.terminal.from}
        durationInFrames={scenes.terminal.duration}
      >
        <TerminalRevealScene lines={data.terminalLines} />
      </Sequence>

      <Sequence
        from={scenes.storyMode.from}
        durationInFrames={scenes.storyMode.duration}
      >
        <StoryModeScene
          stories={data.stories}
          overlay={data.storyOverlay}
        />
      </Sequence>

      <Sequence from={scenes.cta.from} durationInFrames={scenes.cta.duration}>
        <CtaScene url={data.ctaUrl} tagline={data.ctaTagline} />
      </Sequence>

      <NoiseOverlay />
    </AbsoluteFill>
  );
};
