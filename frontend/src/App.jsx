import { useEffect, useState } from "react";
import Home from "./Home.jsx";
import Analyzing from "./Analyzing.jsx";
import Result from "./Result.jsx";
import { scrollToTop } from "./smoothScroll.js";

// analiz başlarken boş ilerleme durumu
const EMPTY_PROGRESS = { title: "", date: "", image: null, source: null, claims: null, results: [], verdict: "" };

export default function App() {
  // hangi ekran görünüyor: "home", "analyzing" ya da "result"
  const [screen, setScreen] = useState("home");
  const [article, setArticle] = useState(null); // sonuç ekranındaki haber
  const [pendingUrl, setPendingUrl] = useState(""); // analiz edilen link
  const [progress, setProgress] = useState(EMPTY_PROGRESS); // analiz sırasında gelen adımlar
  const [recent, setRecent] = useState([]); // son kontroller listesi
  const [error, setError] = useState("");

  // son kontrolleri backend'den yükle
  function loadRecent() {
    fetch("/api/articles")
      .then((res) => res.json())
      .then((list) => setRecent(list))
      .catch(() => setRecent([]));
  }

  useEffect(() => {
    loadRecent();
  }, []);

  function showResult(data) {
    setArticle(data);
    setScreen("result");
    scrollToTop();
  }

  function showError(message) {
    setError(message);
    setScreen("home");
  }

  // yeni bir linki kontrol et. Backend her adımı bitirdikçe haber verir (GET /api/check/stream, SSE);
  // gelen adımlar `progress` içinde birikir ve analiz ekranında canlı gösterilir.
  function checkUrl(url) {
    setError("");
    setPendingUrl(url);
    setProgress(EMPTY_PROGRESS);
    setScreen("analyzing");

    const events = new EventSource("/api/check/stream?url=" + encodeURIComponent(url));
    let finished = false;

    // bir adımın verisini progress'e ekleyen yardımcı
    function onStep(name, apply) {
      events.addEventListener(name, (event) => {
        const data = JSON.parse(event.data);
        setProgress((old) => apply(old, data));
      });
    }

    onStep("fetch_article", (old, data) => ({ ...old, title: data.title, date: data.date, image: data.image }));
    onStep("source_check", (old, data) => ({ ...old, source: data.source }));
    onStep("extract_claims", (old, data) => ({ ...old, claims: data.claims }));
    onStep("check_claim", (old, data) => ({ ...old, results: [...old.results, ...data.results] }));
    onStep("report", (old, data) => ({ ...old, verdict: data.verdict }));

    events.addEventListener("done", (event) => {
      finished = true;
      events.close();
      showResult(JSON.parse(event.data));
      loadRecent();
    });

    // backend'in gönderdiği hata (ör. sayfa çekilemedi)
    events.addEventListener("failed", (event) => {
      finished = true;
      events.close();
      showError(JSON.parse(event.data).detail);
    });

    // bağlantı koptu ya da hiç kurulamadı (kapatmazsak tarayıcı yeniden bağlanıp analizi baştan başlatır)
    events.onerror = () => {
      events.close();
      if (!finished) {
        showError("Sunucuyla bağlantı koptu. Backend çalışıyor mu?");
      }
    };
  }

  // daha önce kontrol edilmiş bir haberi aç (GET /api/article)
  async function openSaved(url) {
    setError("");
    try {
      const res = await fetch("/api/article?url=" + encodeURIComponent(url));
      if (!res.ok) {
        showError("Bu haber bulunamadı.");
        return;
      }
      showResult(await res.json());
    } catch {
      showError("Sunucuya bağlanılamadı. Backend çalışıyor mu?");
    }
  }

  function goHome() {
    setScreen("home");
    setArticle(null);
    scrollToTop();
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="topbar-inner">
          <button type="button" className="brand" onClick={goHome}>
            Fake News Detector
          </button>
          {screen === "result" && (
            <button type="button" className="pill-small" onClick={goHome}>
              Yeni kontrol
            </button>
          )}
        </div>
      </header>

      {screen === "home" && (
        <Home recent={recent} error={error} onCheck={checkUrl} onOpen={openSaved} />
      )}
      {screen === "analyzing" && <Analyzing url={pendingUrl} progress={progress} />}
      {screen === "result" && article && <Result article={article} />}
    </div>
  );
}
