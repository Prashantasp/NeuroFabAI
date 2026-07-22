"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Sparkles,
  Library,
  Network,
  Wrench,
  ShieldCheck,
  BarChart3,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Command Center", href: "/", icon: LayoutDashboard },
  { name: "AI Copilot", href: "/copilot", icon: Sparkles },
  { name: "Knowledge Hub", href: "/hub", icon: Library },
  { name: "Knowledge Graph", href: "/graph", icon: Network },
  { name: "Maintenance Intelligence", href: "/maintenance", icon: Wrench },
  { name: "Compliance Center", href: "/compliance", icon: ShieldCheck },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full w-64 flex-col border-r border-zinc-800 bg-zinc-950 px-4 py-6">
      <div className="flex items-center gap-2 px-2 mb-8">
        <div className="h-8 w-8 rounded bg-cyan-500/20 border border-cyan-500 flex items-center justify-center">
          <Network className="h-5 w-5 text-cyan-500" />
        </div>
        <span className="text-lg font-bold text-zinc-100 tracking-wide">NeuroFab AI</span>
      </div>

      <nav className="flex-1 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-zinc-800/50 text-cyan-400"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
              )}
            >
              <item.icon className={cn("h-5 w-5", isActive ? "text-cyan-400" : "text-zinc-500")} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto pt-4">
        <Link
          href="/settings"
          className={cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            pathname === "/settings"
              ? "bg-zinc-800/50 text-cyan-400"
              : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
          )}
        >
          <Settings className="h-5 w-5 text-zinc-500" />
          Settings
        </Link>
      </div>
    </div>
  );
}
