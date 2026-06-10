"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { Package, BarChart3, LogOut } from "lucide-react";

export function MobileNav() {
  const pathname = usePathname();
  const { data: session } = useSession();

  if (!session) return null;

  const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: Package },
    { href: "/stats", label: "Stats", icon: BarChart3 },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden bg-cyber-surface/95 backdrop-blur-sm border-t border-cyber-border safe-bottom">
      <div className="flex items-center justify-around h-14">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-lg transition-colors ${
                isActive
                  ? "text-cyber-cyan"
                  : "text-cyber-muted active:text-cyber-text"
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-mono">{item.label}</span>
            </Link>
          );
        })}
        <button
          onClick={() => signOut()}
          className="flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-lg text-cyber-muted active:text-cyber-text"
        >
          <LogOut className="w-5 h-5" />
          <span className="text-[10px] font-mono">Sign Out</span>
        </button>
      </div>
    </nav>
  );
}
