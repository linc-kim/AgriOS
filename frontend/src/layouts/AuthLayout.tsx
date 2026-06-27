/**
 * AGRIOS — Auth Layout
 * Used for: Login, OTP verification, PIN setup.
 * Full-screen, centered, no navigation.
 */

import { Outlet } from "react-router-dom";

export default function AuthLayout() {
  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* AGRIOS Logo / Brand area */}
      <div className="flex-shrink-0 px-6 pt-12 pb-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-brand-600 rounded-2xl mb-4">
          <span className="text-white text-2xl font-bold">A</span>
        </div>
        <h1 className="text-xl font-bold text-gray-900">AGRIOS</h1>
        <p className="text-sm text-gray-500 mt-1">Farm Operating System</p>
      </div>

      {/* Screen content */}
      <div className="flex-1 px-6 pb-8">
        <Outlet />
      </div>
    </div>
  );
}
