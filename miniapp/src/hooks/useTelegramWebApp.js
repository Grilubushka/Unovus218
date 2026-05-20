import { useEffect } from "react";

export function useTelegramWebApp() {
  const telegram = window.Telegram?.WebApp;

  useEffect(() => {
    telegram?.ready();
    telegram?.expand();
  }, [telegram]);

  return {
    telegram,
    user: telegram?.initDataUnsafe?.user,
  };
}
