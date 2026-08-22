/* Same-origin soft navigation: replace the app shell, preserve history, no reload. */
(function (global) {
  let controller = null;

  function canNavigate(link, event) {
    if (!link || event.defaultPrevented || event.button !== 0) return false;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
    if (link.target || link.hasAttribute("download")) return false;
    if (link.dataset.fullReload != null) return false;

    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return false;
    if (url.pathname.startsWith("/auth/") || url.pathname === "/logout") return false;
    if (url.pathname.startsWith("/static/")) return false;
    if (url.hash && url.pathname === window.location.pathname && url.search === window.location.search) {
      return false;
    }
    return Boolean(document.querySelector(".app-shell"));
  }

  async function navigate(url, { push = true } = {}) {
    if (controller) controller.abort();
    controller = new AbortController();
    document.documentElement.classList.add("mi-navigating");

    try {
      const response = await fetch(url, {
        method: "GET",
        headers: {
          Accept: "text/html",
          "X-MI-Soft-Navigation": "1",
        },
        credentials: "same-origin",
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(`Navigation failed (${response.status})`);
      const html = await response.text();
      const parsed = new DOMParser().parseFromString(html, "text/html");
      const nextShell = parsed.querySelector(".app-shell");
      const currentShell = document.querySelector(".app-shell");

      // Auth redirects and bare-layout pages must load normally.
      if (!nextShell || !currentShell || response.url.includes("/login")) {
        window.location.assign(response.url || url);
        return;
      }

      currentShell.replaceWith(nextShell);
      document.title = parsed.title || document.title;
      const nextUrl = new URL(url, window.location.href);
      if (push) {
        history.pushState(
          { miSoftNavigation: true },
          "",
          nextUrl.pathname + nextUrl.search + nextUrl.hash
        );
      }
      if (nextUrl.hash) {
        const target = document.getElementById(decodeURIComponent(nextUrl.hash.slice(1)));
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        else window.scrollTo({ top: 0, behavior: "instant" });
      } else {
        window.scrollTo({ top: 0, behavior: "instant" });
      }
      document.dispatchEvent(new CustomEvent("mi:page-loaded", {
        detail: { url: nextUrl.pathname + nextUrl.search + nextUrl.hash },
      }));
    } catch (error) {
      if (error.name !== "AbortError") {
        window.location.assign(url);
      }
    } finally {
      document.documentElement.classList.remove("mi-navigating");
      controller = null;
    }
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!canNavigate(link, event)) return;
    event.preventDefault();
    navigate(link.href);
  });

  window.addEventListener("popstate", () => {
    if (document.querySelector(".app-shell")) navigate(window.location.href, { push: false });
  });

  global.MiNavigation = { navigate };
})(window);
