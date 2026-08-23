import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { DecorativeCorners } from "../article/DecorativeCorners";

interface Props {
  lang: "cs" | "en";
}

export const DayReelOutroSlide: React.FC<Props> = ({ lang }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, 12], [0, 1], {
    extrapolateRight: "clamp",
  });

  const logoSpring = spring({ frame: frame - 8, fps, durationInFrames: 25 });
  const ctaSpring = spring({ frame: frame - 20, fps, durationInFrames: 25 });
  const urlSpring = spring({ frame: frame - 32, fps, durationInFrames: 25 });

  const cta = lang === "cs" ? "Vše čti na" : "Read all on";
  const url = "gamefo.cz";

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
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 64,
            fontWeight: 700,
            color: "#4ecdc4",
            letterSpacing: 8,
            opacity: logoSpring,
            transform: `translateY(${(1 - logoSpring) * -30}px)`,
            textShadow: "0 0 25px rgba(78,205,196,0.4)",
          }}
        >
          GAMEfo
        </div>

        <div
          style={{
            width: 120,
            height: 2,
            background:
              "linear-gradient(90deg, transparent, #4ecdc4, transparent)",
            opacity: ctaSpring,
          }}
        />

        <div
          style={{
            fontFamily: "monospace",
            fontSize: 34,
            color: "#ffffff",
            opacity: ctaSpring,
            transform: `translateY(${(1 - ctaSpring) * 20}px)`,
          }}
        >
          {cta}
        </div>

        <div
          style={{
            fontFamily: "monospace",
            fontSize: 36,
            color: "#4ecdc4",
            opacity: urlSpring,
            transform: `translateY(${(1 - urlSpring) * 20}px)`,
            padding: "12px 32px",
            border: "1px solid rgba(78,205,196,0.4)",
            borderRadius: 8,
          }}
        >
          ▸ {url}
        </div>
      </div>

      <DecorativeCorners />
    </AbsoluteFill>
  );
};
