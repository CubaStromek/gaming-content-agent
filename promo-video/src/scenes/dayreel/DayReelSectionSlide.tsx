import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { DayReelSection } from "../../DayReel";
import { DecorativeCorners } from "../article/DecorativeCorners";

interface Props {
  section: DayReelSection;
  lang: "cs" | "en";
}

export const DayReelSectionSlide: React.FC<Props> = ({ section, lang }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Ken Burns zoom
  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.15], {
    extrapolateRight: "clamp",
  });

  // Crossfade in/out (15 frames)
  const opacity = interpolate(
    frame,
    [0, 15, durationInFrames - 15, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const headingSpring = spring({ frame: frame - 10, fps, durationInFrames: 25 });
  const counterSpring = spring({ frame: frame - 5, fps, durationInFrames: 20 });
  const chipSpring = spring({ frame: frame - 18, fps, durationInFrames: 22 });

  const positionLabel = `${String(section.position).padStart(2, "0")}/${String(section.total).padStart(2, "0")}`;
  const sourceLabel = lang === "cs" ? "gamefo.cz" : "gamefo.cz/en";
  // Krátký game tag — jen když je název 1–3 slova (jinak je to news headline a ruší)
  const gameTag =
    section.gameName && section.gameName.split(" ").length <= 3
      ? section.gameName
      : "";

  return (
    <AbsoluteFill style={{ opacity }}>
      {/* Background (video / image) s Ken Burns */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          overflow: "hidden",
        }}
      >
        {section.isVideo ? (
          <OffthreadVideo
            src={staticFile(`dayreel/${section.mediaFile}`)}
            startFrom={Math.round((section.videoStartSec ?? 0) * fps)}
            muted
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${scale})`,
            }}
          />
        ) : (
          <Img
            src={staticFile(`dayreel/${section.mediaFile}`)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${scale})`,
            }}
          />
        )}
      </div>

      {/* Gradient pro čitelnost */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(180deg, rgba(26,28,30,0.3) 0%, rgba(26,28,30,0.4) 45%, rgba(26,28,30,0.92) 80%, rgba(26,28,30,1) 100%)",
        }}
      />

      {/* Position counter — velký, vpravo nahoře */}
      <div
        style={{
          position: "absolute",
          top: 70,
          right: 60,
          fontFamily: "monospace",
          fontSize: 60,
          fontWeight: 700,
          color: "#4ecdc4",
          letterSpacing: 2,
          opacity: counterSpring,
          transform: `translateY(${(1 - counterSpring) * -20}px)`,
          textShadow: "0 0 20px rgba(78,205,196,0.4)",
        }}
      >
        {positionLabel}
      </div>

      {/* Source badge — vlevo dole */}
      <div
        style={{
          position: "absolute",
          bottom: 60,
          left: 60,
          fontFamily: "monospace",
          fontSize: 22,
          color: "rgba(255,255,255,0.55)",
          letterSpacing: 3,
          opacity: counterSpring,
        }}
      >
        ▸ {sourceLabel}
      </div>

      {/* Game name chip — jen pokud máme čistý krátký název */}
      {gameTag && (
        <div
          style={{
            position: "absolute",
            bottom: 320,
            left: 60,
            fontFamily: "monospace",
            fontSize: 22,
            color: "#4ecdc4",
            letterSpacing: 3,
            opacity: chipSpring,
            transform: `translateX(${(1 - chipSpring) * -20}px)`,
            padding: "6px 14px",
            border: "1px solid rgba(78,205,196,0.5)",
            borderRadius: 4,
            background: "rgba(78,205,196,0.08)",
            textTransform: "uppercase",
          }}
        >
          {gameTag}
        </div>
      )}

      {/* Heading */}
      <div
        style={{
          position: "absolute",
          bottom: 160,
          left: 60,
          right: 60,
        }}
      >
        <div
          style={{
            width: 60,
            height: 3,
            background: "linear-gradient(90deg, #4ecdc4, #2ecc71)",
            marginBottom: 18,
            opacity: headingSpring,
            transform: `scaleX(${headingSpring})`,
            transformOrigin: "left",
          }}
        />
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 36,
            fontWeight: 700,
            color: "#ffffff",
            lineHeight: 1.3,
            opacity: headingSpring,
            transform: `translateY(${(1 - headingSpring) * 30}px)`,
            textShadow: "0 2px 20px rgba(0,0,0,0.85)",
          }}
        >
          {section.heading}
        </div>
      </div>

      <DecorativeCorners />
    </AbsoluteFill>
  );
};
