"use client";

import { signIn } from "next-auth/react";
import Link from "next/link";
import { Package, LogIn } from "lucide-react";

export default function SignInPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-cyber-border bg-cyber-surface/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center">
          <Link href="/" className="flex items-center gap-2">
            <Package className="w-6 h-6 text-cyber-cyan" />
            <span className="font-display font-bold text-lg text-cyber-cyan text-shadow-cyber">
              PARCELSTATS
            </span>
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="cyber-card-glow p-8">
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-6">
                <LogIn className="w-5 h-5 text-cyber-cyan" />
                <h1 className="font-display text-xl text-cyber-cyan">Sign In</h1>
              </div>

              <p className="text-cyber-muted text-sm font-mono mb-6">
                Sign in with your Google account to start tracking packages.
              </p>

              <button
                type="button"
                onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
                className="cyber-btn cyber-btn-primary w-full flex items-center justify-center gap-3"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M21.35 11.1h-9.17v2.73h6.51c-.33 3.81-3.5 5.44-6.5 5.44C8.36 19.27 5 16.25 5 12c0-4.1 3.2-7.27 7.2-7.27 3.09 0 4.9 1.97 4.9 1.97L19 4.72S16.56 2 12.1 2C6.42 2 2.03 6.8 2.03 12c0 5.05 4.13 10 10.22 10 5.35 0 9.25-3.67 9.25-9.09 0-1.15-.15-1.81-.15-1.81Z"
                  />
                </svg>
                Continue with Google
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
