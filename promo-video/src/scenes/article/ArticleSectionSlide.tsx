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
import type { ArticleSection } from "../../ArticleReel";
import { DecorativeCorners } from "./DecorativeCorners";

interface Props {
  section: ArticleSection;
  index: number;
  total: number;
}

export const ArticleSectionSlide: React.FC<Props> = ({
  section,
  index,
  total,
}) => {
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

  // Spring animation for heading text
  const textSpring = spring({ frame: frame - 10, fps, durationInFrames: 25 });

  // Section indicator spring
  const indicatorSpring = spring({
    frame: frame - 5,
    fps,
    durationInFrames: 20,
  });

  return (
    <AbsoluteFill style={{ opacity }}>
      {/* Background (video or screenshot) with Ken Burns */}
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
        {section.videoFile ? (
          <OffthreadVideo
            src={staticFile(`article-reel/${section.videoFile}`)}
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
            src={staticFile(`article-reel/${section.imageFile}`)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${scale})`,
            }}
          />
        )}
      </div>

      {/* Gradient overlay for text readability */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(180deg, rgba(26,28,30,0.2) 0%, rgba(26,28,30,0.3) 50%, rgba(26,28,30,0.9) 80%, rgba(26,28,30,1) 100%)",
        }}
      />

      {/* Section indicator */}
      <div
        style={{
          position: "absolute",
          top: 80,
          left: 60,
          fontFamily: "monospace",
          fontSize: 20,
          color: "#4ecdc4",
          letterSpacing: 3,
          opacity: indicatorSpring,
          transform: `translateX(${(1 - indicatorSpring) * -20}px)`,
        }}
      >
        [{String(index + 1).padStart(2, "0")}/{String(total).padStart(2, "0")}]
      </div>

      {/* Heading text */}
      <div
        style={{
          position: "absolute",
          bottom: 250,
          left: 60,
          right: 60,
        }}
      >
        {/* Accent line */}
        <div
          style={{
            width: 60,
            height: 3,
            background: "linear-gradient(90deg, #4ecdc4, #2ecc71)",
            marginBottom: 20,
            opacity: textSpring,
            transform: `scaleX(${textSpring})`,
            transformOrigin: "left",
          }}
        />

        <div
          style={{
            fontFamily: "monospace",
            fontSize: 44,
            fontWeight: 700,
            color: "#ffffff",
            lineHeight: 1.3,
            opacity: textSpring,
            transform: `translateY(${(1 - textSpring) * 30}px)`,
            textShadow: "0 2px 20px rgba(0,0,0,0.8)",
          }}
        >
          {section.heading}
        </div>
      </div>

      <DecorativeCorners />
    </AbsoluteFill>
  );
};
