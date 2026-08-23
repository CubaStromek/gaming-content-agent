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
import type { ArticleReelData } from "../../ArticleReel";
import { DecorativeCorners } from "./DecorativeCorners";

export const ArticleIntroSlide: React.FC<{ data: ArticleReelData }> = ({
  data,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const startFrom = Math.round((data.featuredVideoStartSec ?? 0) * fps);

  // Ken Burns zoom 1.0 → 1.15
  const scale = interpolate(frame, [0, 90], [1.0, 1.15], {
    extrapolateRight: "clamp",
  });

  // Spring animations for text
  const titleSpring = spring({ frame: frame - 15, fps, durationInFrames: 30 });
  const subtitleSpring = spring({
    frame: frame - 25,
    fps,
    durationInFrames: 30,
  });
  const dateSpring = spring({ frame: frame - 35, fps, durationInFrames: 30 });

  // Fade in
  const fadeIn = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity: fadeIn }}>
      {/* Background image with Ken Burns */}
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
        {data.featuredVideo ? (
          <OffthreadVideo
            src={staticFile(`article-reel/${data.featuredVideo}`)}
            startFrom={startFrom}
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
            src={staticFile(`article-reel/${data.featuredImage}`)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${scale})`,
            }}
          />
        )}
      </div>

      {/* Dark gradient overlay */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(180deg, rgba(26,28,30,0.4) 0%, rgba(26,28,30,0.6) 40%, rgba(26,28,30,0.95) 75%, rgba(26,28,30,1) 100%)",
        }}
      />

      {/* Content */}
      <div
        style={{
          position: "absolute",
          bottom: 200,
          left: 60,
          right: 60,
          display: "flex",
          flexDirection: "column",
          gap: 24,
        }}
      >
        {/* Logo */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 28,
            color: "#4ecdc4",
            letterSpacing: 6,
            textTransform: "uppercase",
            opacity: titleSpring,
            transform: `translateY(${(1 - titleSpring) * 20}px)`,
          }}
        >
          ▸ GAMEfo.cz
        </div>

        {/* Game name / topic */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 32,
            color: "#4ecdc4",
            opacity: titleSpring,
            transform: `translateY(${(1 - titleSpring) * 30}px)`,
            letterSpacing: 2,
          }}
        >
          {data.gameName}
        </div>

        {/* Short title */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 52,
            fontWeight: 700,
            color: "#ffffff",
            lineHeight: 1.2,
            opacity: subtitleSpring,
            transform: `translateY(${(1 - subtitleSpring) * 40}px)`,
            textShadow: "0 2px 20px rgba(0,0,0,0.8)",
          }}
        >
          {data.shortTitle}
        </div>

        {/* Date */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 24,
            color: "rgba(255,255,255,0.6)",
            opacity: dateSpring,
            transform: `translateY(${(1 - dateSpring) * 20}px)`,
          }}
        >
          {data.date}
        </div>
      </div>

      <DecorativeCorners />
    </AbsoluteFill>
  );
};
