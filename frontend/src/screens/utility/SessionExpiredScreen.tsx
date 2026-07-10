import { useNavigate } from "react-router-dom";
import { Clock } from "lucide-react";
import { StatusScreen } from "@/components/ui/StatusScreen";
import { Button } from "@/components/ui/Button";

export default function SessionExpiredScreen() {
  const navigate = useNavigate();
  return (
    <StatusScreen
      icon={<Clock className="h-6 w-6" />}
      title="Your session expired"
      description="For your security you've been signed out after a period of inactivity. Log back in to pick up where you left off."
      action={
        <Button onClick={() => navigate("/login", { replace: true })} size="lg">
          Log back in
        </Button>
      }
    />
  );
}
