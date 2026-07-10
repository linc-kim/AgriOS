/**
 * Greena — Coming Soon Placeholder
 * Used for all tabs not yet built. Replaced sprint-by-sprint.
 */

import { useLocation } from "react-router-dom";

const SCREEN_LABELS: Record<string, { title: string; emoji: string; sprint: string }> = {
  "/flock": { title: "Flock Management", emoji: "🐓", sprint: "Sprint 3" },
  "/health": { title: "Health Management", emoji: "💊", sprint: "Sprint 5" },
  "/finance": { title: "Finance", emoji: "💰", sprint: "Sprint 6" },
  "/aria": { title: "ARIA Assistant", emoji: "🤖", sprint: "Sprint 8" },
  "/notifications": { title: "Notifications", emoji: "🔔", sprint: "Sprint 10" },
  "/settings": { title: "Settings", emoji: "⚙️", sprint: "Sprint 10" },
};

export default function ComingSoonScreen() {
  const { pathname } = useLocation();
  const screen = SCREEN_LABELS[pathname] ?? {
    title: "This screen",
    emoji: "🚧",
    sprint: "A future sprint",
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-8 text-center">
      <span className="text-5xl mb-4">{screen.emoji}</span>
      <h2 className="text-xl font-bold text-gray-900">{screen.title}</h2>
      <p className="text-gray-500 text-sm mt-2">
        Coming in {screen.sprint}
      </p>
    </div>
  );
}
