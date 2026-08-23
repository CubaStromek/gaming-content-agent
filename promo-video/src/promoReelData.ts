export interface PromoStory {
  gameName: string;
  imageFile?: string;
  accentColor: string;
}

export interface PromoReelData {
  hookLine1: string;
  hookLine2: string;
  terminalLines: string[];
  storyOverlay: string;
  stories: PromoStory[];
  ctaUrl: string;
  ctaTagline: string;
}

export const promoReelData: PromoReelData = {
  hookLine1: "Chceš si přečíst o nové hře?",
  hookLine2: "...nebo se utopit v reklamách?",
  terminalLines: [
    "> connect gamefo.cz",
    "> status: clean",
    "> ads: 0",
  ],
  storyOverlay: "STORY MODE — novinky za 30 sekund ⚡",
  stories: [
    { gameName: "Nioh 3", imageFile: "story-1.jpg", accentColor: "#ff4d4d" },
    { gameName: "Crimson Desert", imageFile: "story-2.jpg", accentColor: "#ffaa33" },
    { gameName: "Battlefield 6", imageFile: "story-3.jpg", accentColor: "#4ecdc4" },
  ],
  ctaUrl: "gamefo.cz",
  ctaTagline: "Hry. Bez balastu.",
};

export const PROMO_REEL_CONFIG = {
  fps: 30,
  totalFrames: 360, // 12s
  scenes: {
    hook: { from: 0, duration: 120 }, // 0–4s (3s hook + 1s eskalace)
    reset: { from: 120, duration: 30 }, // 4–5s
    terminal: { from: 150, duration: 60 }, // 5–7s
    storyMode: { from: 210, duration: 90 }, // 7–10s
    cta: { from: 300, duration: 60 }, // 10–12s
  },
};
