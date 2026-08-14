/**
 * Greena — Email verification (from the emailed link).
 *
 * Reads ?token=... and redeems it against /auth/verify-email on load. Email
 * verification is not required to use Greena, so a failed or expired link is not
 * a dead end — we still route the farmer onward.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

import { authAPI } from "@/api/auth";

type Status = "verifying" | "success" | "error" | "notoken";

export default function VerifyEmailScreen() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [status, setStatus] = useState<Status>(token ? "verifying" : "notoken");
  const [email, setEmail] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true; // redeem once — a single-use token must not be double-spent
    authAPI
      .verifyEmail(token)
      .then((res) => {
        setEmail(res.email);
        setStatus("success");
      })
      .catch(() => setStatus("error"));
  }, [token]);

  if (status === "verifying") {
    return (
      <div className="space-y-4 py-6 text-center">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-brand-600" />
        <p className="text-[15px] text-gray-500">Confirming your email…</p>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="space-y-6 text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
          <CheckCircle2 className="h-6 w-6" />
        </span>
        <div>
          <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
            Email confirmed
          </h2>
          <p className="mx-auto mt-2 max-w-sm text-[15px] leading-relaxed text-gray-500">
            {email ? <><span className="font-medium text-gray-700">{email}</span> is verified. </> : "Your email is verified. "}
            You're all set.
          </p>
        </div>
        <Link
          to="/dashboard"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-700"
        >
          Go to my farm <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    );
  }

  // error or notoken — verification isn't required, so guide onward, not into a wall.
  return (
    <div className="space-y-6 text-center">
      <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-amber-600">
        <AlertCircle className="h-6 w-6" />
      </span>
      <div>
        <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
          {status === "notoken" ? "This link looks incomplete" : "This link didn't work"}
        </h2>
        <p className="mx-auto mt-2 max-w-sm text-[15px] leading-relaxed text-gray-500">
          {status === "notoken"
            ? "The verification link is missing its code."
            : "The verification link may have expired or already been used. Don't worry — you can still use Greena, and we can send a fresh link from your settings."}
        </p>
      </div>
      <div className="flex flex-col items-center gap-2">
        <Link
          to="/dashboard"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-700"
        >
          Continue to Greena <ArrowRight className="h-4 w-4" />
        </Link>
        <Link to="/login" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
          Log in
        </Link>
      </div>
    </div>
  );
}
