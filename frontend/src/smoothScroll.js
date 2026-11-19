import Lenis from "lenis";
import "lenis/dist/lenis.css";

let lenis = null;

// Fare tekerleğiyle kaydırmayı yumuşatır.
// İşletim sisteminde "hareketi azalt" açık olan kullanıcılarda normal kaydırma kalır.
export function startSmoothScroll() {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion || lenis) {
    return;
  }
  lenis = new Lenis({
    autoRaf: true, // her karede kendini günceller
    lerp: 0.1, // 0'a yaklaştıkça daha yumuşak ve yavaş
  });
}

// Bir öğeye yumuşakça kaydır; öğe ekranın üst üçte birine gelir.
export function scrollToElement(element) {
  const offset = -Math.round(window.innerHeight / 3);
  if (lenis) {
    lenis.scrollTo(element, { offset: offset, duration: 0.9 });
  } else {
    const top = element.getBoundingClientRect().top + window.scrollY + offset;
    window.scrollTo({ top: top, behavior: "smooth" });
  }
}

// Ekran değişince sayfayı en üste al. Lenis açıkken onun üzerinden yapılmalı,
// yoksa Lenis sayfayı eski konumuna geri kaydırır.
export function scrollToTop() {
  if (lenis) {
    lenis.scrollTo(0, { immediate: true });
  } else {
    window.scrollTo(0, 0);
  }
}
