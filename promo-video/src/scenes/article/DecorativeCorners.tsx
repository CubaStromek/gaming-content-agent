import { useCurrentFrame, interpolate } from "remotion";

const CORNER_SIZE = 30;
const CORNER_THICKNESS = 2;
const MARGIN = 40;
const COLOR = "#4ecdc4";

const Corner: React.FC<{
  top?: boolean;
  left?: boolean;
  opacity: number;
}> = ({ top, left, opacity }) => {
  const style: React.CSSProperties = {
    position: "absolute",
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    opacity,
    ...(top ? { top: MARGIN } : { bottom: MARGIN }),
    ...(left ? { left: MARGIN } : { right: MARGIN }),
    borderColor: COLOR,
    borderStyle: "solid",
    borderWidth: 0,
    ...(top ? { borderTopWidth: CORNER_THICKNESS } : { borderBottomWidth: CORNER_THICKNESS }),
    ...(left ? { borderLeftWidth: CORNER_THICKNESS } : { borderRightWidth: CORNER_THICKNESS }),
  };

  return <div style={style} />;
};

export const DecorativeCorners: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [5, 15], [0, 0.6], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <>
      <Corner top left opacity={opacity} />
      <Corner top opacity={opacity} />
      <Corner left opacity={opacity} />
      <Corner opacity={opacity} />
    </>
  );
};
