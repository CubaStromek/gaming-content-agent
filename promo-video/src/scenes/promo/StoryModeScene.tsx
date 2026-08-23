import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { PromoStory } from "../../promoReelData";

const STORY_DURATION = 30; // 1s @ 30fps
const PHONE_WIDTH = 720;
const PHONE_HEIGHT = 1480;

const StoryCard: React.FC<{ story: PromoStory; index: number; activeIndex: number; localFrame: number; fps: number }> = ({
  story,
  index,
  activeIndex,
  localFrame,
  fps,
}) => {
  const offset = index - activeIndex;

  const transitionProgress = spring({
    frame: localFrame,
    fps,
    config: { damping: 200, stiffness: 180 },
  });

  const yPercent = (offset - (1 - transitionProgress)) * 100;

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        transform: `translateY(${yPercent}%)`,
        background: `linear-gradient(135deg, ${story.accentColor}33, #000)`,
        overflow: "hidden",
      }}
    >
      {story.imageFile && (
        <Img
          src={staticFile(`promo-reel/${story.imageFile}`)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: 0.85,
          }}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      )}

      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.2) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.85) 100%)",
        }}
      />

      <div
        style={{
          position: "absolute",
          bottom: 60,
          left: 40,
          right: 40,
          color: "#fff",
        }}
      >
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 22,
            color: story.accentColor,
            letterSpacing: 4,
            marginBottom: 12,
          }}
        >
          ▸ NEW
        </div>
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontSize: 64,
            fontWeight: 900,
            lineHeight: 1.0,
            letterSpacing: -1,
          }}
        >
          {story.gameName}
        </div>
      </div>

      {/* IG-style story progress bars */}
      <div
        style={{
          position: "absolute",
          top: 30,
          left: 30,
          right: 30,
          display: "flex",
          gap: 6,
        }}
      >
        {[0, 1, 2].map((i) => {
          const filled = i < activeIndex ? 1 : i === activeIndex ? Math.min(1, localFrame / STORY_DURATION) : 0;
          return (
            <div
              key={i}
              style={{
                flex: 1,
                height: 4,
                background: "rgba(255,255,255,0.3)",
                borderRadius: 2,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${filled * 100}%`,
                  height: "100%",
                  background: "#fff",
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};

const ThumbHint: React.FC<{ frame: number }> = ({ frame }) => {
  const cycle = frame % STORY_DURATION;
  const opacity = interpolate(cycle, [0, 8, 22, 30], [0, 0.7, 0.7, 0]);
  const y = interpolate(cycle, [0, 30], [40, -40]);
  return (
    <div
      style={{
        position: "absolute",
        right: 40,
        bottom: 200,
        opacity,
        transform: `translateY(${y}px)`,
        fontSize: 80,
        filter: "drop-shadow(0 4px 20px rgba(0,0,0,0.8))",
        zIndex: 10,
      }}
    >
      👆
    </div>
  );
};

export const StoryModeScene: React.FC<{
  stories: PromoStory[];
  overlay: string;
}> = ({ stories, overlay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const activeIndex = Math.min(stories.length - 1, Math.floor(frame / STORY_DURATION));
  const localFrame = frame - activeIndex * STORY_DURATION;

  const overlayOpacity = interpolate(frame, [0, 12, 70, 88], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: "#000",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Phone frame */}
      <div
        style={{
          width: PHONE_WIDTH,
          height: PHONE_HEIGHT,
          background: "#000",
          borderRadius: 60,
          border: "8px solid #1a1a1a",
          boxShadow: "0 20px 80px rgba(0,255,136,0.15), 0 0 0 4px #2a2a2a",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {stories.map((story, i) => (
          <StoryCard
            key={i}
            story={story}
            index={i}
            activeIndex={activeIndex}
            localFrame={localFrame}
            fps={fps}
          />
        ))}
        <ThumbHint frame={frame} />
      </div>

      {/* Overlay text above phone */}
      <div
        style={{
          position: "absolute",
          top: 80,
          left: 0,
          right: 0,
          textAlign: "center",
          fontFamily: "Inter, sans-serif",
          fontSize: 44,
          fontWeight: 900,
          color: "#00ff88",
          letterSpacing: -0.5,
          textShadow: "0 0 30px rgba(0,255,136,0.6)",
          opacity: overlayOpacity,
          padding: "0 60px",
          lineHeight: 1.2,
        }}
      >
        {overlay}
      </div>
    </AbsoluteFill>
  );
};
