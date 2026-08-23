import {
  AbsoluteFill,
  interpolate,
  random,
  useCurrentFrame,
} from "remotion";

const FakeBrowserChrome: React.FC = () => (
  <div
    style={{
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      height: 120,
      background: "#2a2a2a",
      display: "flex",
      alignItems: "center",
      padding: "0 30px",
      gap: 16,
      zIndex: 10,
    }}
  >
    <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#ff5f57" }} />
    <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#febc2e" }} />
    <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#28c840" }} />
    <div
      style={{
        flex: 1,
        height: 50,
        background: "#1a1a1a",
        borderRadius: 25,
        marginLeft: 30,
        display: "flex",
        alignItems: "center",
        paddingLeft: 30,
        color: "#888",
        fontFamily: "monospace",
        fontSize: 22,
      }}
    >
      🔒 random-gaming-blog.cz
    </div>
  </div>
);

const TopBannerAd: React.FC<{ frame: number }> = ({ frame }) => {
  const flicker = 0.7 + Math.sin(frame * 0.8) * 0.3;
  return (
    <div
      style={{
        position: "absolute",
        top: 120,
        left: 0,
        right: 0,
        height: 220,
        background: `linear-gradient(135deg, #ff006e ${flicker * 50}%, #fb5607 100%)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        zIndex: 20,
        boxShadow: "0 4px 20px rgba(255,0,110,0.5)",
      }}
    >
      <div style={{ fontSize: 48, fontWeight: 900, color: "#fff", letterSpacing: 2 }}>
        💰 SÁZKY ZDARMA! 💰
      </div>
      <div style={{ fontSize: 28, color: "#fff", marginTop: 8 }}>
        BONUS 5000 Kč ▸ KLIKNI TEĎ!
      </div>
    </div>
  );
};

const FakeContent: React.FC = () => (
  <div
    style={{
      position: "absolute",
      top: 360,
      left: 40,
      right: 40,
      zIndex: 5,
      opacity: 0.4,
    }}
  >
    <div style={{ height: 60, background: "#444", borderRadius: 8, marginBottom: 20, width: "85%" }} />
    <div style={{ height: 24, background: "#333", borderRadius: 4, marginBottom: 12, width: "100%" }} />
    <div style={{ height: 24, background: "#333", borderRadius: 4, marginBottom: 12, width: "95%" }} />
    <div style={{ height: 24, background: "#333", borderRadius: 4, marginBottom: 12, width: "70%" }} />
  </div>
);

const AutoPlayVideoAd: React.FC<{ frame: number }> = ({ frame }) => (
  <div
    style={{
      position: "absolute",
      top: 700,
      left: 60,
      right: 60,
      height: 380,
      background: "#000",
      border: "4px solid #00d9ff",
      zIndex: 25,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexDirection: "column",
      boxShadow: `0 0 40px rgba(0,217,255,${0.4 + Math.sin(frame * 0.3) * 0.3})`,
    }}
  >
    <div style={{ fontSize: 36, color: "#00d9ff", fontWeight: 700 }}>▶ REKLAMA</div>
    <div style={{ fontSize: 24, color: "#fff", marginTop: 16, opacity: 0.7 }}>
      Přeskočit za {Math.max(0, 15 - Math.floor(frame / 6))}s
    </div>
    <div
      style={{
        position: "absolute",
        top: 12,
        right: 12,
        width: 36,
        height: 36,
        borderRadius: "50%",
        background: "rgba(255,255,255,0.2)",
        color: "#fff",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 20,
      }}
    >
      ✕
    </div>
  </div>
);

const NotificationPopup: React.FC<{ frame: number; delay: number }> = ({ frame, delay }) => {
  const opacity = interpolate(frame, [delay, delay + 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const slideY = interpolate(frame, [delay, delay + 12], [-50, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        top: 1180,
        left: 40,
        right: 40,
        background: "#fff",
        borderRadius: 16,
        padding: 24,
        zIndex: 30,
        opacity,
        transform: `translateY(${slideY}px)`,
        boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
      }}
    >
      <div style={{ fontSize: 28, fontWeight: 700, color: "#000", marginBottom: 8 }}>
        🔔 Povolíte oznámení?
      </div>
      <div style={{ fontSize: 22, color: "#555" }}>
        Nepropásněte žádný článek!
      </div>
      <div
        style={{
          marginTop: 16,
          display: "flex",
          gap: 12,
        }}
      >
        <div style={{ flex: 1, height: 50, background: "#0066ff", borderRadius: 8, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 600 }}>
          POVOLIT
        </div>
        <div style={{ flex: 1, height: 50, background: "#eee", borderRadius: 8, color: "#666", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>
          Blokovat
        </div>
      </div>
    </div>
  );
};

const SubscribePopup: React.FC<{ frame: number; delay: number }> = ({ frame, delay }) => {
  const opacity = interpolate(frame, [delay, delay + 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = interpolate(frame, [delay, delay + 8], [0.7, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        top: 600,
        left: 80,
        right: 80,
        background: "#1a1a2e",
        border: "3px solid #ffbe0b",
        borderRadius: 20,
        padding: 40,
        zIndex: 40,
        opacity,
        transform: `scale(${scale})`,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 48, fontWeight: 900, color: "#ffbe0b", marginBottom: 12 }}>
        SUBSCRIBE!
      </div>
      <div style={{ fontSize: 24, color: "#fff" }}>
        Newsletter každý den ✉️
      </div>
    </div>
  );
};

const CookieBar: React.FC = () => (
  <div
    style={{
      position: "absolute",
      bottom: 0,
      left: 0,
      right: 0,
      background: "rgba(0,0,0,0.95)",
      borderTop: "2px solid #00ff88",
      padding: 30,
      zIndex: 50,
    }}
  >
    <div style={{ fontSize: 22, color: "#fff", marginBottom: 16 }}>
      🍪 Tato stránka používá 247 cookies. Vážíme si vašeho soukromí, ale potřebujeme všechno.
    </div>
    <div style={{ display: "flex", gap: 12 }}>
      <div style={{ flex: 1, height: 60, background: "#00ff88", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "#000", fontSize: 22, fontWeight: 700 }}>
        SOUHLASÍM SE VŠÍM
      </div>
      <div style={{ width: 60, height: 60, background: "#222", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "#666", fontSize: 18 }}>
        ⚙
      </div>
    </div>
  </div>
);

const GlitchText: React.FC<{ text: string; frame: number; visible: boolean }> = ({
  text,
  frame,
  visible,
}) => {
  if (!visible) return null;
  const offsetX = (random(`g${Math.floor(frame / 2)}`) - 0.5) * 8;
  const offsetY = (random(`g${Math.floor(frame / 2)}b`) - 0.5) * 4;
  return (
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: 0,
        right: 0,
        transform: "translateY(-50%)",
        textAlign: "center",
        zIndex: 100,
        fontFamily: "Inter, sans-serif",
        fontSize: 76,
        fontWeight: 900,
        color: "#fff",
        textShadow: `${offsetX}px ${offsetY}px 0 #ff0044, ${-offsetX}px ${-offsetY}px 0 #00d9ff`,
        padding: "0 40px",
        lineHeight: 1.1,
        letterSpacing: -1,
      }}
    >
      {text}
    </div>
  );
};

export const HookFrustrationScene: React.FC<{
  line1: string;
  line2: string;
}> = ({ line1, line2 }) => {
  const frame = useCurrentFrame();

  const showLine1 = frame >= 8 && frame < 90;
  const showLine2 = frame >= 95;

  const staticBurst =
    frame > 110
      ? Math.floor(random(`s${frame}`) * 255)
      : null;

  const cameraShake =
    frame > 60 ? (random(`shake${frame}`) - 0.5) * (frame > 100 ? 14 : 6) : 0;

  return (
    <AbsoluteFill
      style={{
        background: "#fff",
        transform: `translate(${cameraShake}px, ${cameraShake * 0.5}px)`,
      }}
    >
      <FakeBrowserChrome />
      <TopBannerAd frame={frame} />
      <FakeContent />
      <AutoPlayVideoAd frame={frame} />
      <NotificationPopup frame={frame} delay={20} />
      <SubscribePopup frame={frame} delay={75} />
      <CookieBar />

      <GlitchText text={line1} frame={frame} visible={showLine1} />
      <GlitchText text={line2} frame={frame} visible={showLine2} />

      {staticBurst !== null && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `rgb(${staticBurst},${staticBurst},${staticBurst})`,
            opacity: 0.15,
            mixBlendMode: "difference",
            zIndex: 200,
          }}
        />
      )}
    </AbsoluteFill>
  );
};
