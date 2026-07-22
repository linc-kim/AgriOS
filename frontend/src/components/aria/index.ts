/**
 * ARIA design system — one import path for every AI surface in Greena.
 *
 * The mark itself lives in `components/brand/AriaMark` and is re-exported here;
 * that file is the identity, this folder is the product built on it. Screens
 * should import from here, never reach past it into the brand layer.
 */

/* Identity */
export { AriaMark, AriaLockup, type AriaState, type AriaTone, type AriaDetail } from "@/components/brand/AriaMark";
export { AriaIcon, AriaAvatar, AriaBadge, AriaStatus } from "./AriaIdentity";
export { AriaFloatingButton } from "./AriaFloatingButton";

/* Waiting */
export { AriaThinking, AriaLoading, AriaTypingDots } from "./AriaFeedback";
export { AriaEmptyState } from "./AriaEmptyState";

/* Trust signals */
export {
  AriaConfidence,
  AriaSourceBadge,
  AriaSources,
  AriaRiskChip,
  AriaTrendChip,
  AriaFactors,
} from "./AriaSignals";

/* Cards */
export {
  AriaCard,
  AriaPredictionCard,
  AriaDiseaseCard,
  AriaForecastCard,
  AriaRecommendation,
  AriaInsightCard,
  AriaHeadline,
  type AriaRecommendationItem,
  type AriaInsightItem,
} from "./AriaCards";

/* Conversation */
export {
  AriaMessageBubble,
  AriaFollowUps,
  AriaQuickActions,
  AriaComposer,
  AriaTranscript,
  type AriaMessage,
} from "./AriaChat";
export { suggestFollowUps, OPENING_ACTIONS } from "./followUps";

/* Vocabulary */
export {
  CONFIDENCE,
  RISK,
  SEVERITY,
  MOTION,
  confidenceSwatch,
  riskSwatch,
  severitySwatch,
  trendSwatch,
  normaliseTrend,
  label,
  type AriaConfidenceLevel,
  type AriaRiskLevel,
  type AriaSeverity,
  type AriaTrend,
} from "./tokens";
