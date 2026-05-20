import { useRef, useState } from "react";

import { useApp } from "../AppContext.jsx";
import { BottomNav } from "../BottomNav.jsx";
import { Toast } from "../Toast.jsx";
import { Topbar } from "../Topbar.jsx";

const ACCEPTED_TYPES = ".pdf,image/*,.png,.jpg,.jpeg,.webp";
const MAX_FILE_SIZE = 12 * 1024 * 1024;

export function Certificates() {
  const { showToast, toast } = useApp();

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <main className="certificates-page" aria-labelledby="certificates-title">
          <section className="page-hero compact">
            <span className="eyebrow">Сертификаты</span>
            <h1 id="certificates-title">Загрузка сертификатов</h1>
            <p>Добавляй PDF или изображения, чтобы собрать портфель подтверждений рядом с учебным прогрессом.</p>
          </section>
          <CertificatesSection />
        </main>
      </div>
      <BottomNav />
      <Toast message={toast} />
    </>
  );
}

export function CertificatesSection() {
  const { certificates, showToast, uploadCertificate } = useApp();
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  async function handleFileChange(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (file.size > MAX_FILE_SIZE) {
      showToast("Файл больше 12 МБ. Загрузи PDF или изображение поменьше.");
      return;
    }

    setUploading(true);
    try {
      await uploadCertificate(file);
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="certificates-section" aria-labelledby="certificates-section-title">
      <div className="section-head compact">
        <h2 id="certificates-section-title">Сертификаты</h2>
        <span>{certificates.length} всего</span>
      </div>

      <section className="upload-panel">
        <div className="upload-copy">
          <span className="upload-icon">▣</span>
          <div>
            <h2>Новый сертификат</h2>
            <p>Название берётся из имени файла. После загрузки он появится в списке и откроет достижение.</p>
          </div>
        </div>
        <input ref={inputRef} className="sr-only" type="file" accept={ACCEPTED_TYPES} onChange={handleFileChange} />
        <button className="btn primary upload-action" type="button" disabled={uploading} onClick={() => inputRef.current?.click()}>
          {uploading ? "Загружаю..." : "Выбрать файл"}
        </button>
      </section>

      <section className="certificate-list" aria-label="Загруженные сертификаты">
        {certificates.length > 0 ? (
          certificates.map((certificate) => <CertificateCard key={`${certificate.source}-${certificate.id}`} certificate={certificate} />)
        ) : (
          <div className="empty-state">
            <strong>Пока пусто</strong>
            <span>Загрузи первый файл, и здесь появится карточка сертификата.</span>
          </div>
        )}
      </section>
    </section>
  );
}

function CertificateCard({ certificate }) {
  return (
    <article className="certificate-card">
      <div className="certificate-mark" aria-hidden="true">
        {fileLabel(certificate.file_type)}
      </div>
      <div>
        <h3>{certificate.title}</h3>
        <p>{certificateMeta(certificate)}</p>
      </div>
    </article>
  );
}

function fileLabel(fileType) {
  if (fileType?.includes("pdf")) return "PDF";
  if (fileType?.startsWith("image/")) return "IMG";
  return "DOC";
}

function certificateMeta(certificate) {
  const uploadedAt = certificate.uploaded_at ? new Date(certificate.uploaded_at).toLocaleDateString("ru-RU") : "";
  return [certificate.file_type, uploadedAt, certificate.source === "miniapp-local" ? "локально" : "сервер"].filter(Boolean).join(" · ");
}
