import { Composition } from "remotion";
import { ArticleReel, ARTICLE_REEL_CONFIG, computeArticleReelTotalFrames } from "./ArticleReel";
import { ArticleReelEN } from "./ArticleReelEN";
import { articleReelData } from "./articleReelData";
import { articleReelDataEN } from "./articleReelDataEN";
import { DayReel, DAYREEL_CONFIG, computeDayreelTotalFrames } from "./DayReel";
import { dayReelData } from "./dayReelData";
import { dayReelDataEN } from "./dayReelDataEN";
import { PromoReel } from "./PromoReel";
import { promoReelData, PROMO_REEL_CONFIG } from "./promoReelData";

const calcFrames = (sectionCount: number) => {
  const { introDuration, sectionDuration, outroDuration } = ARTICLE_REEL_CONFIG;
  return introDuration + sectionCount * sectionDuration + outroDuration;
};


export const Root: React.FC = () => {
  const { fps } = ARTICLE_REEL_CONFIG;

  return (
    <>
      <Composition
        id="ArticleReel"
        component={ArticleReel}
        durationInFrames={computeArticleReelTotalFrames(articleReelData)}
        fps={fps}
        width={1080}
        height={1920}
        defaultProps={{ data: articleReelData }}
      />
      <Composition
        id="ArticleReelEN"
        component={ArticleReelEN}
        durationInFrames={calcFrames(articleReelDataEN.sections.length)}
        fps={fps}
        width={1080}
        height={1920}
        defaultProps={{ data: articleReelDataEN }}
      />
      <Composition
        id="DayReel"
        component={DayReel}
        durationInFrames={computeDayreelTotalFrames(dayReelData)}
        fps={DAYREEL_CONFIG.fps}
        width={1080}
        height={1920}
        defaultProps={{ data: dayReelData }}
      />
      <Composition
        id="DayReelEN"
        component={DayReel}
        durationInFrames={computeDayreelTotalFrames(dayReelDataEN)}
        fps={DAYREEL_CONFIG.fps}
        width={1080}
        height={1920}
        defaultProps={{ data: dayReelDataEN }}
      />
      <Composition
        id="PromoReel"
        component={PromoReel}
        durationInFrames={PROMO_REEL_CONFIG.totalFrames}
        fps={PROMO_REEL_CONFIG.fps}
        width={1080}
        height={1920}
        defaultProps={{ data: promoReelData }}
      />
    </>
  );
};
