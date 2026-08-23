import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ArticleIntroSlide } from "./scenes/article/ArticleIntroSlide";
import { ArticleSectionSlide } from "./scenes/article/ArticleSectionSlide";
import { ArticleOutroSlide } from "./scenes/article/ArticleOutroSlide";

export interface ArticleSection {
  heading: string;
  imageFile: string;
  videoFile?: string;
  videoStartSec?: number;
  narrationFile?: string | null;
  narrationDurationSec?: number;
}

export interface ArticleReelData {
  articleTitle: string;
  shortTitle: string;
  gameName: string;
  date: string;
  articleUrl: string;
  featuredImage: string;
  featuredVideo?: string;
  featuredVideoStartSec?: number;
  sections: ArticleSection[];
  introNarrationFile?: string | null;
  introNarrationDurationSec?: number;
  outroNarrationFile?: string | null;
  outroNarrationDurationSec?: number;
}

export const ARTICLE_REEL_CONFIG = {
  fps: 30,
  introDuration: 90, // 3s (silent fallback)
  sectionDuration: 105, // 3.5s (silent fallback)
  outroDuration: 120, // 4s (silent fallback)
  crossfadeDuration: 15, // 0.5s
  // Narrator padding (frames added around narration so text breathes)
  narrationPaddingHead: 6, // 0.2s
  narrationPaddingTail: 15, // 0.5s
};

// --- Duration helpers (sdílené s Root.tsx) ---

const framesForNarration = (
  durationSec: number,
  fps: number,
  fallback: number,
): number => {
  if (!durationSec || durationSec <= 0) return fallback;
  return (
    Math.ceil(durationSec * fps) +
    ARTICLE_REEL_CONFIG.narrationPaddingHead +
    ARTICLE_REEL_CONFIG.narrationPaddingTail
  );
};

export const computeArticleReelTimings = (data: ArticleReelData) => {
  const { fps, introDuration, sectionDuration, outroDuration } =
    ARTICLE_REEL_CONFIG;
  const intro = framesForNarration(
    data.introNarrationDurationSec ?? 0,
    fps,
    introDuration,
  );
  const outro = framesForNarration(
    data.outroNarrationDurationSec ?? 0,
    fps,
    outroDuration,
  );
  const sections = data.sections.map((s) =>
    framesForNarration(s.narrationDurationSec ?? 0, fps, sectionDuration),
  );
  const total = intro + sections.reduce((a, b) => a + b, 0) + outro;
  return { intro, sections, outro, total };
};

export const computeArticleReelTotalFrames = (data: ArticleReelData): number =>
  computeArticleReelTimings(data).total;

const COLORS = {
  bg: "#1a1c1e",
  teal: "#4ecdc4",
  green: "#2ecc71",
  text: "#e0e0e0",
  textBright: "#ffffff",
  accent: "#4ecdc4",
};

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
          background: `linear-gradient(90deg, ${COLORS.teal}, ${COLORS.green})`,
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

export const ArticleReel: React.FC<{ data: ArticleReelData }> = ({ data }) => {
  const timings = computeArticleReelTimings(data);
  const { narrationPaddingHead } = ARTICLE_REEL_CONFIG;

  let cursor = 0;
  const introStart = cursor;
  cursor += timings.intro;
  const sectionStarts = timings.sections.map((dur) => {
    const start = cursor;
    cursor += dur;
    return start;
  });
  const outroStart = cursor;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      {/* Intro */}
      <Sequence from={introStart} durationInFrames={timings.intro}>
        <ArticleIntroSlide data={data} />
      </Sequence>
      {data.introNarrationFile && (
        <Sequence from={introStart + narrationPaddingHead}>
          <Audio src={staticFile(`narration/${data.introNarrationFile}`)} />
        </Sequence>
      )}

      {/* Sections */}
      {data.sections.map((section, i) => {
        const sectionStart = sectionStarts[i];
        const sectionDur = timings.sections[i];
        return (
          <Sequence key={i} from={sectionStart} durationInFrames={sectionDur}>
            <ArticleSectionSlide
              section={section}
              index={i}
              total={data.sections.length}
            />
            {section.narrationFile && (
              <Sequence from={narrationPaddingHead}>
                <Audio src={staticFile(`narration/${section.narrationFile}`)} />
              </Sequence>
            )}
          </Sequence>
        );
      })}

      {/* Outro */}
      <Sequence from={outroStart} durationInFrames={timings.outro}>
        <ArticleOutroSlide />
      </Sequence>
      {data.outroNarrationFile && (
        <Sequence from={outroStart + narrationPaddingHead}>
          <Audio src={staticFile(`narration/${data.outroNarrationFile}`)} />
        </Sequence>
      )}

      <ScanlineOverlay />
      <ProgressBar />
    </AbsoluteFill>
  );
};
