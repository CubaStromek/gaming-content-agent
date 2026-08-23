import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const NEON = "#00ff88";

export const CtaScene: React.FC<{ url: string; tagline: string }> = ({
  url,
  tagline,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoSpring = spring({ frame, fps, config: { damping: 12, stiffness: 100 } });
  const urlSpring = spring({ frame: frame - 12, fps, durationInFrames: 30 });
  const taglineSpring = spring({ frame: frame - 24, fps, durationInFrames: 30 });

  const glowIntensity = 0.6 + Math.sin(frame * 0.15) * 0.3;

  const bassPulse = interpolate(frame, [0, 8, 20], [1.3, 1.0, 1.0], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: "#000",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Radial spotlight */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(circle at center, rgba(0,255,136,${0.15 * glowIntensity}) 0%, transparent 60%)`,
        }}
      />

      {/* Logo "GAMEfo.cz" */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 120,
          fontWeight: 900,
          color: NEON,
          letterSpacing: -2,
          textShadow: `0 0 40px ${NEON}, 0 0 80px ${NEON}80, 0 0 120px ${NEON}40`,
          transform: `scale(${logoSpring * bassPulse})`,
          opacity: logoSpring,
          marginBottom: 40,
        }}
      >
        GAMEfo
      </div>

      {/* URL */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 56,
          color: "#fff",
          letterSpacing: 4,
          opacity: urlSpring,
          transform: `translateY(${(1 - urlSpring) * 20}px)`,
          marginBottom: 60,
        }}
      >
        {url}
      </div>

      {/* Tagline */}
      <div
        style={{
          fontFamily: "Inter, sans-serif",
          fontSize: 38,
          fontWeight: 600,
          color: "rgba(255,255,255,0.7)",
          letterSpacing: 1,
          opacity: taglineSpring,
          transform: `translateY(${(1 - taglineSpring) * 15}px)`,
        }}
      >
        {tagline}
      </div>

      {/* Bottom corner brackets */}
      <div
        style={{
          position: "absolute",
          bottom: 80,
          left: 80,
          width: 60,
          height: 60,
          borderLeft: `4px solid ${NEON}`,
          borderBottom: `4px solid ${NEON}`,
          opacity: 0.6,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 80,
          right: 80,
          width: 60,
          height: 60,
          borderRight: `4px solid ${NEON}`,
          borderBottom: `4px solid ${NEON}`,
          opacity: 0.6,
        }}
      />
    </AbsoluteFill>
  );
};
