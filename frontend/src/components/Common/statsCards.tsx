import React from "react";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { HelpCircle } from "lucide-react";

export type StatCardColor = "cyan" | "emerald" | "red" | "orange" | "amber";

export type StatCardItem = {
  heading: string;
  subheading?: string;
  value: React.ReactNode;
  icon: LucideIcon;
  color?: StatCardColor;
  tooltip?: string | null;
};

type StatsCardsProps = {
  items: StatCardItem[];
  transition: { duration: number };
  reduceMotion: boolean | null;
};

function iconClass(color: StatCardColor | undefined) {
  switch (color) {
    case "emerald":
      return "text-emerald-400";
    case "red":
      return "text-red-400";
    case "orange":
      return "text-orange-400";
    case "amber":
      return "text-amber-400";
    default:
      return "text-cyan-400";
  }
}

export default function StatsCards({ items, transition, reduceMotion }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {items.map((item, i) => {
        const Icon = item.icon;
        const color = item.color ?? "cyan";
        return (
          <motion.div
            key={`${item.heading}-${item.subheading ?? ""}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...transition, delay: reduceMotion ? 0 : i * 0.05 }}
            whileHover={reduceMotion ? undefined : { y: -2, transition: { duration: 0.15 } }}
            className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4 hover:border-neutral-700 transition-colors group relative"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-neutral-400 uppercase tracking-wider flex items-center gap-1">
                {item.heading}
                {item.tooltip ? (
                  <span
                    title={item.tooltip}
                    className="text-neutral-500 hover:text-neutral-300 cursor-help"
                  >
                    <HelpCircle size={12} />
                  </span>
                ) : null}
              </span>
              <Icon size={18} className={iconClass(color)} />
            </div>
            <div className="text-2xl font-bold text-white">{item.value}</div>
            {item.subheading ? (
              <div className="text-xs text-neutral-500 mt-0.5">{item.subheading}</div>
            ) : null}
          </motion.div>
        );
      })}
    </div>
  );
}
