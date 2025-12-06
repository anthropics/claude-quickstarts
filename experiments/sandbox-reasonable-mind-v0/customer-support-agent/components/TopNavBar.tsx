"use client";
import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import Image from "next/image";
import { Moon, Sun, Check } from "lucide-react";
import { useTheme } from "next-themes";
import { themes } from "@/styles/themes";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const themeColors = {
  neutral: "#000000",
  red: "#EF4444",
  violet: "#8B5CF6",
  blue: "#3B82F6",
  tangerine: "#F97316",
  emerald: "#10B981",
  amber: "#F59E0B",
} as const;

type ThemeName = keyof typeof themes;

const ColorCircle = ({
  themeName,
  isSelected,
}: {
  themeName: ThemeName;
  isSelected: boolean;
}) => (
  <div
    className="relative border flex h-4 w-4 shrink-0 items-center justify-center rounded-full"
    style={{ backgroundColor: themeColors[themeName] }}
  >
    {isSelected && (
      <div className="absolute inset-0 flex items-center justify-center">
        <Check className="text-white" size={12} />
      </div>
    )}
  </div>
);

const TopNavBar = () => {
  const { theme, setTheme } = useTheme();
  const [colorTheme, setColorTheme] = useState<ThemeName>("neutral");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const savedColorTheme = (localStorage.getItem("color-theme") ||
      "neutral") as ThemeName;
    setColorTheme(savedColorTheme);
    applyTheme(savedColorTheme, theme === "dark");
  }, [theme]);

  const applyTheme = (newColorTheme: ThemeName, isDark: boolean) => {
    const root = document.documentElement;
    const themeVariables = isDark
      ? themes[newColorTheme].dark
      : themes[newColorTheme].light;

    Object.entries(themeVariables).forEach(([key, value]) => {
      root.style.setProperty(`--${key}`, value as string);
    });
  };

  const handleThemeChange = (newColorTheme: ThemeName) => {
    setColorTheme(newColorTheme);
    localStorage.setItem("color-theme", newColorTheme);
    applyTheme(newColorTheme, theme === "dark");
  };

  const handleModeChange = (mode: "light" | "dark" | "system") => {
    setTheme(mode);
    if (mode !== "system") {
      applyTheme(colorTheme, mode === "dark");
    }
  };

  if (!mounted) {
    return null;
  }

  return (
    <nav className="text-foreground p-4 flex justify-between items-center">
      <div className="font-bold text-xl flex gap-2 items-center">
        <Image
          src={theme === "dark" ? "/wordmark-dark.svg" : "/wordmark.svg"}
          alt="Company Wordmark"
          width={112}
          height={20}
        />
      </div>
      <div className="flex items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">
              <ColorCircle themeName={colorTheme} isSelected={false} />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {(Object.keys(themes) as ThemeName[]).map((themeName) => (
              <DropdownMenuItem
                key={themeName}
                onClick={() => handleThemeChange(themeName)}
                className="flex items-center gap-2"
              >
                <ColorCircle
                  themeName={themeName}
                  isSelected={colorTheme === themeName}
                />
                {themeName.charAt(0).toUpperCase() + themeName.slice(1)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon">
              <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              <span className="sr-only">Toggle theme</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleModeChange("light")}>
              Light
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleModeChange("dark")}>
              Dark
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleModeChange("system")}>
              System
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Link
          href="https://github.com/anthropics/anthropic-quickstarts"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button variant="outline" className="text-foreground">
            Deploy your own
          </Button>
        </Link>
      </div>
    </nav>
  );
};

export default TopNavBar;
