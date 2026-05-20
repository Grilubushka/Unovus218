import Lottie from "lottie-react";
import coinAnimation from "../assets/coin.json"; 
import { useApp } from "./AppContext.jsx";

export function Topbar({ onToast }) {
  const app = useApp();
  const coinBalance = app?.coinBalance ?? 128;

  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo" aria-hidden="true" />
        <div>
          <p className="brand-title">Прогрессоры</p>
          {/* <p className="brand-subtitle">ИИ-маршрут обучения</p> */}
        </div>
      </div>
      <button
        className="coin"
        type="button"
        onClick={() => onToast("Прокоины начисляются за темы, практику, тесты и серию дней.")}
      >
        <Lottie
          animationData={coinAnimation}
          loop={true}
          autoplay={true}
          style={{ width: 28, height: 28 }}
        /> {coinBalance}
      </button>
    </header>
  );
}
