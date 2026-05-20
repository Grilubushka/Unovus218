export function Toast({ message }) {
  return (
    <div id="toast" className={`toast ${message ? "show" : ""}`} role="status">
      {message}
    </div>
  );
}
