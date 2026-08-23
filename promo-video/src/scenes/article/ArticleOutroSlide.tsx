import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { DecorativeCorners } from "./DecorativeCorners";

export const ArticleOutroSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  const logoSpring = spring({ frame: frame - 10, fps, durationInFrames: 30 });
  const ctaSpring = spring({ frame: frame - 25, fps, durationInFrames: 30 });
  const urlSpring = spring({ frame: frame - 40, fps, durationInFrames: 30 });

  // Glitch effect on logo — brief horizontal offset
  const glitchOffset =
    frame > 20 && frame < 25
      ? Math.sin(frame * 15) * 4
      : frame > 60 && frame < 64
        ? Math.sin(frame * 12) * 3
        : 0;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#1a1c1e",
        opacity: fadeIn,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      {/* Terminal grid background */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          backgroundImage:
            "linear-gradient(rgba(78,205,196,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(78,205,196,0.03) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 40,
        }}
      >
        {/* Logo with glitch */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 64,
            fontWeight: 700,
            color: "#4ecdc4",
            letterSpacing: 8,
            opacity: logoSpring,
            transform: `translateX(${glitchOffset}px) translateY(${(1 - logoSpring) * -30}px)`,
            textShadow:
              glitchOffset !== 0
                ? "2px 0 #ff0000, -2px 0 #00ff00"
                : "0 0 20px rgba(78,205,196,0.3)",
          }}
        >
          GAMEfo
        </div>

        {/* Divider line */}
        <div
          style={{
            width: 120,
            height: 2,
            background: "linear-gradient(90deg, transparent, #4ecdc4, transparent)",
            opacity: ctaSpring,
          }}
        />

        {/* CTA */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 36,
            color: "#ffffff",
            textAlign: "center",
            lineHeight: 1.4,
            opacity: ctaSpring,
            transform: `translateY(${(1 - ctaSpring) * 20}px)`,
          }}
        >
          Celý článek čti na
        </div>

        {/* URL */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 32,
            color: "#4ecdc4",
            opacity: urlSpring,
            transform: `translateY(${(1 - urlSpring) * 20}px)`,
            padding: "12px 32px",
            border: "1px solid rgba(78,205,196,0.3)",
            borderRadius: 8,
          }}
        >
          gamefo.cz
        </div>
      </div>

      <DecorativeCorners />
    </AbsoluteFill>
  );
};
