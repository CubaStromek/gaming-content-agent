import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { ArticleIntroSlide } from "./scenes/article/ArticleIntroSlide";
import { ArticleSectionSlide } from "./scenes/article/ArticleSectionSlide";
import { ArticleOutroSlideEN } from "./scenes/article/ArticleOutroSlideEN";
import type { ArticleReelData } from "./ArticleReel";
import { ARTICLE_REEL_CONFIG } from "./ArticleReel";

const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const progress = frame / durationInFrames;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        width: "100%",
        height: 4,
        background: "rgba(255,255,255,0.1)",
        zIndex: 100,
      }}
    >
      <div
        style={{
          width: `${progress * 100}%`,
          height: "100%",
          background: "linear-gradient(90deg, #4ecdc4, #2ecc71)",
        }}
      />
    </div>
  );
};

const ScanlineOverlay: React.FC = () => (
  <div
    style={{
      position: "absolute",
      top: 0,
      left: 0,
      width: "100%",
      height: "100%",
      backgroundImage:
        "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)",
      pointerEvents: "none",
      zIndex: 90,
    }}
  />
);

export const ArticleReelEN: React.FC<{ data: ArticleReelData }> = ({ data }) => {
  const { introDuration, sectionDuration, outroDuration } =
    ARTICLE_REEL_CONFIG;

  return (
    <AbsoluteFill style={{ backgroundColor: "#1a1c1e" }}>
      <Sequence from={0} durationInFrames={introDuration}>
        <ArticleIntroSlide data={data} />
      </Sequence>

      {data.sections.map((section, i) => {
        const sectionStart = introDuration + i * sectionDuration;
        return (
          <Sequence
            key={i}
            from={sectionStart}
            durationInFrames={sectionDuration}
          >
            <ArticleSectionSlide
              section={section}
              index={i}
              total={data.sections.length}
            />
          </Sequence>
        );
      })}

      <Sequence
        from={introDuration + data.sections.length * sectionDuration}
        durationInFrames={outroDuration}
      >
        <ArticleOutroSlideEN />
      </Sequence>

      <ScanlineOverlay />
      <ProgressBar />
    </AbsoluteFill>
  );
};
