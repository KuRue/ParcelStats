"use client";

import Link from "next/link";
import { useSession, signOut } from "next-auth/react";
import { Package, BarChart3, LogOut, Menu, X, Shield } from "lucide-react";
import { useState } from "react";

export function Navbar() {
  const { data: session } = useSession();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="border-b border-cyber-border bg-cyber-surface/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <Package className="w-6 h-6 text-cyber-cyan" />
          <span className="font-display font-bold text-lg text-cyber-cyan text-shadow-cyber">
            PARCELSTATS
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          {session && (
            <>
              <Link
                href="/dashboard"
                className="text-sm text-cyber-muted hover:text-cyber-cyan transition-colors font-mono"
              >
                Dashboard
              </Link>
              <Link
                href="/stats"
                className="text-sm text-cyber-muted hover:text-cyber-cyan transition-colors font-mono"
              >
                <BarChart3 className="w-4 h-4 inline mr-1" />
                Stats
              </Link>
              {session.user?.isAdmin && (
                <Link
                  href="/admin"
                  className="text-sm text-cyber-muted hover:text-cyber-green transition-colors font-mono"
                >
                  <Shield className="w-4 h-4 inline mr-1" />
                  Admin
                </Link>
              )}
            </>
          )}
          {session ? (
            <div className="flex items-center gap-3">
              <span className="text-xs text-cyber-muted font-mono">
                {session.user?.email}
              </span>
              <button
                onClick={() => signOut()}
                className="cyber-btn text-xs py-1 px-3"
              >
                <LogOut className="w-3 h-3 mr-1 inline" />
                Sign Out
              </button>
            </div>
          ) : (
            <a href="/api/auth/signin" className="cyber-btn text-sm">
              Sign In
            </a>
          )}
        </nav>

        <button
          className="md:hidden text-cyber-muted"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="md:hidden border-t border-cyber-border bg-cyber-surface p-4">
          <nav className="flex flex-col gap-3">
            {session && (
              <>
                <Link
                  href="/dashboard"
                  className="text-sm text-cyber-muted hover:text-cyber-cyan font-mono"
                  onClick={() => setMobileOpen(false)}
                >
                  Dashboard
                </Link>
                <Link
                  href="/stats"
                  className="text-sm text-cyber-muted hover:text-cyber-cyan font-mono"
                  onClick={() => setMobileOpen(false)}
                >
                  Stats
                </Link>
                {session.user?.isAdmin && (
                  <Link
                    href="/admin"
                    className="text-sm text-cyber-muted hover:text-cyber-green font-mono"
                    onClick={() => setMobileOpen(false)}
                  >
                    Admin
                  </Link>
                )}
              </>
            )}
            {session ? (
              <button
                onClick={() => { signOut(); setMobileOpen(false); }}
                className="cyber-btn text-sm w-fit"
              >
                Sign Out
              </button>
            ) : (
              <a href="/api/auth/signin" className="cyber-btn text-sm w-fit">
                Sign In
              </a>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
