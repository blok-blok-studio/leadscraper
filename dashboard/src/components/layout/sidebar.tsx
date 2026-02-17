"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Activity,
  Download,
  Zap,
  Crosshair,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/scrape", label: "Scrape Control", icon: Crosshair },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/jobs", label: "Scrape Jobs", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col bg-sidebar-bg text-sidebar-fg">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b border-white/10 px-6">
        <Zap className="h-6 w-6 text-sidebar-active" />
        <span className="text-lg font-bold">LeadScraper</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-sidebar-active text-white"
                  : "text-sidebar-fg/70 hover:bg-white/10 hover:text-white"
              }`}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Export */}
      <div className="border-t border-white/10 p-3">
        <a
          href="/api/export?format=csv"
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-fg/70 transition-colors hover:bg-white/10 hover:text-white"
        >
          <Download className="h-5 w-5" />
          Export CSV
        </a>
      </div>

      <div className="border-t border-white/10 px-6 py-3">
        <p className="text-xs text-sidebar-fg/50">Bloblok Studio</p>
      </div>
    </aside>
  );
}
