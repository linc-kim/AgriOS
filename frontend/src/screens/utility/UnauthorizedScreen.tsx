import { useNavigate } from "react-router-dom";
import { ShieldOff } from "lucide-react";
import { StatusScreen } from "@/components/ui/StatusScreen";
import { Button } from "@/components/ui/Button";

export default function UnauthorizedScreen() {
  const navigate = useNavigate();
  return (
    <StatusScreen
      icon={<ShieldOff className="h-6 w-6" />}
      title="You don't have access to this"
      description="Your role doesn't permit viewing this area. If you think this is a mistake, contact your organization owner."
      action={
        <Button onClick={() => navigate("/")} size="lg">
          Back to dashboard
        </Button>
      }
    />
  );
}
