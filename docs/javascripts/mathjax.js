// SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
// SPDX-License-Identifier: Apache-2.0

let katexLoadingPromise = null;

function renderMath() {
  if (typeof renderMathInElement === "function") {
    renderMathInElement(document.body, {
      delimiters: [
        { left: "$$",  right: "$$",  display: true },
        { left: "$",   right: "$",   display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true }
      ],
      throwOnError: false
    });
  }
}

function loadKaTeX() {
  if (katexLoadingPromise) {
    return katexLoadingPromise;
  }

  katexLoadingPromise = new Promise((resolve, reject) => {
    // 1. Inject KaTeX CSS with SRI
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css";
    link.integrity = "sha384-nB0miv6/jRmo5UMMR1wu3Gz6NLsoTkbqJghGIsx//Rlm+ZU03BU6SQNC66uf4l5+";
    link.crossOrigin = "anonymous";
    link.onerror = (err) => {
      console.warn("[Zenzic] Failed to load KaTeX stylesheet:", err);
    };
    document.head.appendChild(link);

    // 2. Inject KaTeX Core JS with SRI
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js";
    script.integrity = "sha384-7zkQWkzuo3B5mTepMUcHkMB5jZaolc2xDwL6VFqjFALcbeS9Ggm/Yr2r3Dy4lfFg";
    script.crossOrigin = "anonymous";
    script.onerror = (err) => {
      console.warn("[Zenzic] Failed to load KaTeX core script:", err);
      reject(err);
    };

    script.onload = () => {
      // 3. Inject KaTeX Auto-render Extension with SRI
      const autoRender = document.createElement("script");
      autoRender.src = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js";
      autoRender.integrity = "sha384-43gviWU0YVjaDtb/GhzOouOXtZMP/7XUzwPTstBeZFe/+rCMvRwr4yROQP43s0Xk";
      autoRender.crossOrigin = "anonymous";
      autoRender.onerror = (err) => {
        console.warn("[Zenzic] Failed to load KaTeX auto-render extension:", err);
        reject(err);
      };
      autoRender.onload = () => {
        resolve();
      };
      document.head.appendChild(autoRender);
    };

    document.head.appendChild(script);
  });

  return katexLoadingPromise;
}

document$.subscribe(() => {
  if (document.querySelector(".arithmatex")) {
    loadKaTeX()
      .then(() => renderMath())
      .catch((err) => {
        console.warn("[Zenzic] Math rendering skipped due to KaTeX load error:", err);
      });
  }
});

