import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

const NEON = "#00ff88";
const CHARS_PER_FRAME = 0.6;
const LINE_GAP_FRAMES = 6;

export const TerminalRevealScene: React.FC<{ lines: string[] }> = ({ lines }) => {
  const frame = useCurrentFrame();

  let charBudget = frame * CHARS_PER_FRAME;

  const renderedLines = lines.map((line, i) => {
    if (i > 0) charBudget -= LINE_GAP_FRAMES * CHARS_PER_FRAME;
    const visibleChars = Math.max(0, Math.min(line.length, Math.floor(charBudget)));
    charBudget -= line.length;
    return line.slice(0, visibleChars);
  });

  const cursorOn = Math.floor(frame / 8) % 2 === 0;

  const flashOpacity = interpolate(frame, [0, 4], [1, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: "#000",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "flex-start",
        padding: "0 80px",
        fontFamily: "monospace",
        fontSize: 64,
        fontWeight: 700,
        color: NEON,
        textShadow: `0 0 20px ${NEON}, 0 0 40px ${NEON}80`,
        letterSpacing: 2,
      }}
    >
      <div style={{ position: "absolute", inset: 0, background: "#fff", opacity: flashOpacity, zIndex: 10 }} />

      {renderedLines.map((text, i) => {
        const isLast = i === renderedLines.length - 1;
        const showCursor = isLast && text.length === lines[i].length;
        return (
          <div key={i} style={{ marginBottom: 24, minHeight: 80 }}>
            {text}
            {showCursor && (
              <span style={{ opacity: cursorOn ? 1 : 0, marginLeft: 4 }}>▋</span>
            )}
            {!showCursor && isLast && text.length < lines[i].length && (
              <span style={{ opacity: cursorOn ? 1 : 0, marginLeft: 4 }}>▋</span>
            )}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
