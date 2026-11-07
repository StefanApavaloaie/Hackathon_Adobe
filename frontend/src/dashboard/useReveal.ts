// Owned by frontend/Stefan. Fades sections in as they scroll into view.
// Content is visible by default: only elements below the fold are hidden, and only when
// IntersectionObserver exists and the visitor has not asked for reduced motion.
import { useEffect } from "react";

export function useReveal() {
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) return;

    const targets = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
    const below = targets.filter((el) => el.getBoundingClientRect().top > window.innerHeight * 0.92);

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          (entry.target as HTMLElement).dataset.reveal = "shown";
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.18, rootMargin: "0px 0px -6% 0px" },
    );

    for (const el of below) {
      el.dataset.reveal = "pending";
      observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);
}
