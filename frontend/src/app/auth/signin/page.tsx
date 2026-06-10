"use client";

import { useState, useEffect } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Package, LogIn, Loader2, AlertCircle, Mail, Lock, User, UserPlus } from "lucide-react";

export default function SignInPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasGoogle, setHasGoogle] = useState(false);

  useEffect(() => {
    fetch("/api/auth/providers")
      .then((r) => (r.ok ? r.json() : {}))
      .then((providers: Record<string, unknown>) => setHasGoogle(!!providers?.google))
      .catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const formData = new FormData(e.currentTarget);
    const email = formData.get("email") as string;
    const password = formData.get("password") as string;

    if (isRegister) {
      const name = formData.get("name") as string;

      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.error || "Registration failed");
        setLoading(false);
        return;
      }
    }

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    if (result?.error) {
      setError(isRegister ? "Account created but sign-in failed. Please try again." : "Invalid email or password");
      setLoading(false);
      return;
    }

    router.push("/dashboard");
  }

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
                {isRegister ? (
                  <UserPlus className="w-5 h-5 text-cyber-cyan" />
                ) : (
                  <LogIn className="w-5 h-5 text-cyber-cyan" />
                )}
                <h1 className="font-display text-xl text-cyber-cyan">
                  {isRegister ? "Create Account" : "Sign In"}
                </h1>
              </div>

              <div className="mb-6 flex border border-cyber-border rounded overflow-hidden">
                <button
                  type="button"
                  onClick={() => { setIsRegister(false); setError(""); }}
                  className={`flex-1 py-2 text-sm font-mono tracking-wide transition-all ${
                    !isRegister
                      ? "bg-cyber-cyan/20 text-cyber-cyan border-b-2 border-cyber-cyan"
                      : "text-cyber-muted hover:text-cyber-text"
                  }`}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => { setIsRegister(true); setError(""); }}
                  className={`flex-1 py-2 text-sm font-mono tracking-wide transition-all ${
                    isRegister
                      ? "bg-cyber-cyan/20 text-cyber-cyan border-b-2 border-cyber-cyan"
                      : "text-cyber-muted hover:text-cyber-text"
                  }`}
                >
                  Register
                </button>
              </div>

              {error && (
                <div className="mb-4 flex items-center gap-2 text-cyber-red text-sm font-mono bg-cyber-red/10 border border-cyber-red/30 rounded px-3 py-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {error}
                </div>
              )}

              {hasGoogle && (
                <>
                  <button
                    type="button"
                    onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
                    className="cyber-btn w-full flex items-center justify-center gap-2 mb-4"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
                      <path fill="currentColor" d="M21.35 11.1h-9.17v2.73h6.51c-.33 3.81-3.5 5.44-6.5 5.44C8.36 19.27 5 16.25 5 12c0-4.1 3.2-7.27 7.2-7.27 3.09 0 4.9 1.97 4.9 1.97L19 4.72S16.56 2 12.1 2C6.42 2 2.03 6.8 2.03 12c0 5.05 4.13 10 10.22 10 5.35 0 9.25-3.67 9.25-9.09 0-1.15-.15-1.81-.15-1.81Z" />
                    </svg>
                    Continue with Google
                  </button>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="flex-1 h-px bg-cyber-border/50" />
                    <span className="text-[10px] text-cyber-muted font-mono">OR</span>
                    <div className="flex-1 h-px bg-cyber-border/50" />
                  </div>
                </>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {isRegister && (
                  <div>
                    <label className="block text-xs font-mono text-cyber-muted tracking-wide mb-1">
                      Name
                    </label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-cyber-muted" />
                      <input
                        name="name"
                        type="text"
                        required
                        placeholder="Your name"
                        className="cyber-input w-full pl-10"
                      />
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-mono text-cyber-muted tracking-wide mb-1">
                    Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-cyber-muted" />
                    <input
                      name="email"
                      type="email"
                      required
                      placeholder="you@example.com"
                      className="cyber-input w-full pl-10"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-mono text-cyber-muted tracking-wide mb-1">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-cyber-muted" />
                    <input
                      name="password"
                      type="password"
                      required
                      minLength={8}
                      placeholder="••••••••"
                      className="cyber-input w-full pl-10"
                    />
                  </div>
                  {isRegister && (
                    <p className="mt-1 text-xs text-cyber-muted font-mono">
                      Minimum 8 characters
                    </p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="cyber-btn cyber-btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <LogIn className="w-4 h-4" />
                  )}
                  {isRegister ? "Create Account" : "Sign In"}
                </button>
              </form>
            </div>
          </div>

          <p className="mt-4 text-center text-xs text-cyber-muted font-mono">
            {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
            <button
              onClick={() => { setIsRegister(!isRegister); setError(""); }}
              className="text-cyber-cyan hover:underline"
            >
              {isRegister ? "Sign in" : "Create one"}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}
