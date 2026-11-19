import { useState } from "react";
import { articleTone, formatDate } from "./labels.js";

// Giriş ekranı: link kutusu ve son kontroller
export default function Home({ recent, error, onCheck, onOpen }) {
  const [url, setUrl] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    const trimmed = url.trim();
    if (trimmed) {
      onCheck(trimmed);
    }
  }

  return (
    <main className="home">
      <section className="hero">
        <h1>
          Her iddia.
          <br />
          Kanıtıyla.
        </h1>
        <p className="hero-text">
          Bir haber linki yapıştırın. İddiaları tek tek araştırıp kararını kaynaklarıyla gösterelim.
        </p>

        <form className="search" onSubmit={handleSubmit}>
          <label htmlFor="news-url" className="visually-hidden">
            Haber linki
          </label>
          <input
            id="news-url"
            type="url"
            required
            placeholder="Haber linkini yapıştırın"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
          <button type="submit" className="pill">
            Kontrol et
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      {recent.length > 0 && (
        <section className="recent">
          <h2>Son kontroller</h2>
          <ul>
            {recent.map((item) => (
              <li key={item.url}>
                <button type="button" className="recent-item" onClick={() => onOpen(item.url)}>
                  {item.image && <img src={item.image} alt="" className="recent-thumb" />}
                  <span className="recent-text">
                    <span className="recent-title">{item.title}</span>
                    <span className="muted">
                      {item.domain} · {formatDate(item.checked_at, false)}
                    </span>
                  </span>
                  <span className={"recent-verdict tone-" + articleTone(item.verdict)}>
                    <span className="dot" />
                    {item.verdict}
                    {item.kind && item.kind !== item.verdict && " · " + item.kind}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
