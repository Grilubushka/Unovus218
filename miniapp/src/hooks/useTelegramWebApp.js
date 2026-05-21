import { useEffect } from "react";

export function useTelegramWebApp() {
  const telegram = window.Telegram?.WebApp;
  const query = new URLSearchParams(window.location.search);
  const user = telegram?.initDataUnsafe?.user;
  const userId = normalizeUserId(
    user?.id ??
      query.get("telegram_user_id") ??
      query.get("user_id") ??
      telegram?.initDataUnsafe?.start_param,
  );

  useEffect(() => {
    telegram?.ready();
    telegram?.expand();
  }, [telegram]);

  return {
    telegram,
    user,
    userId,
  };
}

function normalizeUserId(value) {
  if (value === null || value === undefined) {
    return "";
  }

  const normalized = String(value).trim();
  return /^\d+$/.test(normalized) ? normalized : "";
}
