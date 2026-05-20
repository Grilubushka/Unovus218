const MATERIAL_ICONS = {
  video: "🎬",
  practice: "🧩",
  quiz: "🧪",
  article: "📄",
};

export function iconFor(format) {
  return MATERIAL_ICONS[format] ?? "📌";
}
