"use client";

import { Bell, Search, User } from "lucide-react";
import { usePathname } from "next/navigation";

export function Header() {
  const pathname = usePathname();
  
  const getTitle = () => {
    switch (pathname) {
      case "/": return "Command Center";
      case "/copilot": return "AI Copilot";
      case "/hub": return "Knowledge Hub";
      case "/graph": return "Knowledge Graph";
      case "/maintenance": return "Maintenance Intelligence";
      case "/compliance": return "Compliance Center";
      case "/analytics": return "Analytics";
      case "/settings": return "Settings";
      default: return "Command Center";
    }
  };

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-zinc-100">{getTitle()}</h1>
      </div>

      <div className="flex items-center gap-4">
        {/* Search Bar Shortcut */}
        <div className="hidden md:flex items-center gap-2 rounded-md bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-zinc-400">
          <Search className="h-4 w-4" />
          <span>Search...</span>
          <kbd className="ml-2 rounded bg-zinc-800 px-1.5 py-0.5 text-xs font-medium font-mono">⌘K</kbd>
        </div>

        <button className="relative rounded-full p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors">
          <Bell className="h-5 w-5" />
          <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-cyan-500 ring-2 ring-zinc-950" />
        </button>
        
        <div className="h-8 w-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300">
          <User className="h-4 w-4" />
        </div>
      </div>
    </header>
  );
}
