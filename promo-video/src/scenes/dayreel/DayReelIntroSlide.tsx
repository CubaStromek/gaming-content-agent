import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { DayReelData } from "../../DayReel";
import { DecorativeCorners } from "../article/DecorativeCorners";

const formatDateCs = (iso: string): string => {
  // "2026-05-03" → "3.5.2026"
  const [y, m, d] = iso.split("-");
  return `${parseInt(d, 10)}.${parseInt(m, 10)}.${y}`;
};

const formatDateEn = (iso: string): string => {
  // "2026-05-03" → "MAY 3"
  const months = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
  ];
  const [, m, d] = iso.split("-");
  return `${months[parseInt(m, 10) - 1]} ${parseInt(d, 10)}`;
};

export const DayReelIntroSlide: React.FC<{ data: DayReelData }> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });

  const logoSpring = spring({ frame: frame - 5, fps, durationInFrames: 25 });
  const dateSpring = spring({ frame: frame - 15, fps, durationInFrames: 25 });
  const subSpring = spring({ frame: frame - 25, fps, durationInFrames: 25 });

  const dateLabel = data.lang === "cs" ? formatDateCs(data.date) : formatDateEn(data.date);
  const subLabel =
    data.lang === "cs"
      ? `${data.sections.length} ČLÁNK${data.sections.length === 1 ? "" : data.sections.length < 5 ? "Y" : "Ů"} DNES`
      : `${data.sections.length} STORIES TODAY`;
  const headline = data.lang === "cs" ? "DNES NA GAMEFO" : "TODAY ON GAMEFO";

  // Glitch logo
  const glitchOffset =
    frame > 12 && frame < 17
      ? Math.sin(frame * 14) * 4
      : frame > 40 && frame < 44
        ? Math.sin(frame * 11) * 3
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
      {/* Terminal grid */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          backgroundImage:
            "linear-gradient(rgba(78,205,196,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(78,205,196,0.04) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 36,
        }}
      >
        {/* Logo s glitchem */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 56,
            fontWeight: 700,
            color: "#4ecdc4",
            letterSpacing: 8,
            opacity: logoSpring,
            transform: `translateX(${glitchOffset}px) translateY(${(1 - logoSpring) * -20}px)`,
            textShadow:
              glitchOffset !== 0
                ? "2px 0 #ff0000, -2px 0 #00ff00"
                : "0 0 20px rgba(78,205,196,0.3)",
          }}
        >
          GAMEfo
        </div>

        {/* Headline */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 32,
            color: "#ffffff",
            letterSpacing: 4,
            opacity: dateSpring,
            transform: `translateY(${(1 - dateSpring) * 20}px)`,
          }}
        >
          {headline}
        </div>

        {/* Date — velký, zvýraznění */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 96,
            fontWeight: 700,
            color: "#4ecdc4",
            opacity: dateSpring,
            transform: `translateY(${(1 - dateSpring) * 30}px)`,
            textShadow: "0 0 30px rgba(78,205,196,0.4)",
          }}
        >
          {dateLabel}
        </div>

        {/* Sub label */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 28,
            color: "rgba(255,255,255,0.7)",
            letterSpacing: 3,
            opacity: subSpring,
            transform: `translateY(${(1 - subSpring) * 20}px)`,
            padding: "10px 24px",
            border: "1px solid rgba(78,205,196,0.4)",
            borderRadius: 6,
          }}
        >
          ▸ {subLabel}
        </div>
      </div>

      <DecorativeCorners />
    </AbsoluteFill>
  );
};
