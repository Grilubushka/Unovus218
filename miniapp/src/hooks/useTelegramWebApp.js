import { useEffect } from "react";

export function useTelegramWebApp() {
  useEffect(() => {
    const telegram = window.Telegram?.WebApp;
    telegram?.ready();
    telegram?.expand();
  }, []);
}
