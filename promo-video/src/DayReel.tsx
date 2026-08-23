import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { DayReelIntroSlide } from "./scenes/dayreel/DayReelIntroSlide";
import { DayReelSectionSlide } from "./scenes/dayreel/DayReelSectionSlide";
import { DayReelOutroSlide } from "./scenes/dayreel/DayReelOutroSlide";

export interface DayReelSection {
  heading: string;
  gameName: string;
  position: number;
  total: number;
  mediaFile: string;
  isVideo: boolean;
  videoStartSec?: number;
  narrationFile?: string | null;
  narrationDurationSec?: number;
}

export interface DayReelData {
  date: string;
  lang: "cs" | "en";
  musicFile: string;
  introNarrationFile?: string | null;
  introNarrationDurationSec?: number;
  outroNarrationFile?: string | null;
  outroNarrationDurationSec?: number;
  sections: DayReelSection[];
}

export const DAYREEL_CONFIG = {
  fps: 30,
  // Silent-mode default durations (frames)
  introDuration: 60, // 2s
  sectionDuration: 105, // 3.5s
  outroDuration: 90, // 3s
  // Narrator padding (frames added around narration audio so text breathes)
  narrationPaddingHead: 6, // 0.2s
  narrationPaddingTail: 12, // 0.4s
};

const COLORS = {
  bg: "#1a1c1e",
  teal: "#4ecdc4",
  green: "#2ecc71",
};

// --- Duration helpers (sdílené s Root.tsx) ---

const framesForNarration = (durationSec: number, fps: number, fallback: number): number => {
  if (!durationSec || durationSec <= 0) return fallback;
  return (
    Math.ceil(durationSec * fps) +
    DAYREEL_CONFIG.narrationPaddingHead +
    DAYREEL_CONFIG.narrationPaddingTail
  );
};

export const computeDayreelTimings = (data: DayReelData) => {
  const { fps, introDuration, sectionDuration, outroDuration } = DAYREEL_CONFIG;

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

export const computeDayreelTotalFrames = (data: DayReelData): number =>
  computeDayreelTimings(data).total;

// --- Components ---

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

export const DayReel: React.FC<{ data: DayReelData }> = ({ data }) => {
  const timings = computeDayreelTimings(data);
  const hasNarrator = Boolean(data.introNarrationFile);

  // Hudba: bez narátora normální fade in/out na 0.6.
  // S narátorem: hudba úplně ztišena (volume 0) — uživatelské zadání.
  const audioVolume = (frame: number) => {
    if (hasNarrator) return 0;
    return interpolate(
      frame,
      [0, 30, timings.total - 45, timings.total],
      [0, 0.6, 0.6, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
  };

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
      {/* Hudba — vždy přítomná (ztišená při narátoru, fade jinak) */}
      <Audio src={staticFile(`audio/${data.musicFile}`)} volume={audioVolume} />

      {/* Intro */}
      <Sequence from={introStart} durationInFrames={timings.intro}>
        <DayReelIntroSlide data={data} />
      </Sequence>
      {data.introNarrationFile && (
        <Sequence from={introStart + DAYREEL_CONFIG.narrationPaddingHead}>
          <Audio src={staticFile(`narration/${data.introNarrationFile}`)} />
        </Sequence>
      )}

      {/* Sections */}
      {data.sections.map((section, i) => {
        const sectionStart = sectionStarts[i];
        const sectionDur = timings.sections[i];
        return (
          <Sequence key={i} from={sectionStart} durationInFrames={sectionDur}>
            <DayReelSectionSlide section={section} lang={data.lang} />
            {section.narrationFile && (
              <Sequence from={DAYREEL_CONFIG.narrationPaddingHead}>
                <Audio src={staticFile(`narration/${section.narrationFile}`)} />
              </Sequence>
            )}
          </Sequence>
        );
      })}

      {/* Outro */}
      <Sequence from={outroStart} durationInFrames={timings.outro}>
        <DayReelOutroSlide lang={data.lang} />
      </Sequence>
      {data.outroNarrationFile && (
        <Sequence from={outroStart + DAYREEL_CONFIG.narrationPaddingHead}>
          <Audio src={staticFile(`narration/${data.outroNarrationFile}`)} />
        </Sequence>
      )}

      <ScanlineOverlay />
      <ProgressBar />
    </AbsoluteFill>
  );
};
