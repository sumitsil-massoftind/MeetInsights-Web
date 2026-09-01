/* Bearer API client. Refresh credentials remain HttpOnly and never enter JS. */
(function (global) {
  const TOKEN_KEY = "mi_bearer_token";
  const HANDOFF_COOKIE = "mi_bearer_handoff";
  const REFRESH_URL = "/api/auth/refresh";
  let refreshPromise = null;

  function readCookie(name) {
    const prefix = `${encodeURIComponent(name)}=`;
    const part = document.cookie
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith(prefix));
    return part ? decodeURIComponent(part.slice(prefix.length)) : "";
  }

  function clearHandoffCookie() {
    document.cookie = `${HANDOFF_COOKIE}=; Max-Age=0; path=/; SameSite=Lax`;
  }

  function getAccessToken() {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  }

  function setAccessToken(token) {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  }

  function importHandoffToken() {
    const token = readCookie(HANDOFF_COOKIE);
    if (token) {
      setAccessToken(token);
      clearHandoffCookie();
    }
    return token;
  }

  async function readEnvelope(response) {
    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = null;
      }
    }
    const envelope = payload && payload.response ? payload.response : {};
    const status = envelope.status || {};
    return {
      payload,
      data: envelope.data == null ? {} : envelope.data,
      status,
      msg: status.msg || "Request failed.",
      ok: response.ok && status.action_status !== false,
    };
  }

  async function refreshAccessToken() {
    if (refreshPromise) return refreshPromise;
    refreshPromise = (async () => {
      const previousToken = getAccessToken();
      const headers = {
        Accept: "application/json",
        "Content-Type": "application/json",
      };
      if (previousToken) headers.Authorization = `Bearer ${previousToken}`;
      const response = await fetch(REFRESH_URL, {
        method: "POST",
        headers,
        credentials: "same-origin",
        body: "{}",
      });
      const result = await readEnvelope(response);
      const token = result.ok && result.data.access_token;
      if (!token) {
        setAccessToken("");
        return false;
      }
      setAccessToken(token);
      clearHandoffCookie();
      return true;
    })().finally(() => {
      refreshPromise = null;
    });
    return refreshPromise;
  }

  async function apiFetch(url, options = {}, retried = false) {
    let token = getAccessToken() || importHandoffToken();
    if (!token && !retried) {
      const refreshed = await refreshAccessToken();
      if (refreshed) token = getAccessToken();
    }

    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    if (token) headers.set("Authorization", `Bearer ${token}`);

    let response = await fetch(url, {
      ...options,
      headers,
      credentials: "same-origin",
    });

    if (response.status === 401 && !retried && url !== REFRESH_URL) {
      if (await refreshAccessToken()) {
        return apiFetch(url, options, true);
      }
    }
    return response;
  }

  async function getJson(url) {
    const response = await apiFetch(url, { method: "GET" });
    const result = await readEnvelope(response);
    if (!result.ok) {
      const error = new Error(result.msg);
      error.status = response.status;
      error.data = result.data;
      throw error;
    }
    return result;
  }

  async function postJson(url, body) {
    const response = await apiFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body == null ? {} : body),
    });
    const result = await readEnvelope(response);
    if (!result.ok) {
      const error = new Error(result.msg);
      error.status = response.status;
      error.data = result.data;
      throw error;
    }
    return result;
  }

  async function deleteJson(url) {
    const response = await apiFetch(url, { method: "DELETE" });
    const result = await readEnvelope(response);
    if (!result.ok) {
      const error = new Error(result.msg);
      error.status = response.status;
      error.data = result.data;
      throw error;
    }
    return result;
  }

  async function postForm(url, body) {
    const response = await apiFetch(url, { method: "POST", body });
    const result = await readEnvelope(response);
    if (!result.ok) {
      const error = new Error(result.msg);
      error.status = response.status;
      error.data = result.data;
      throw error;
    }
    return result;
  }

  importHandoffToken();
  document.addEventListener("click", (event) => {
    if (event.target.closest('a[href="/logout"]')) setAccessToken("");
  });

  global.MiAuth = {
    apiFetch,
    deleteJson,
    getAccessToken,
    getJson,
    postForm,
    postJson,
    refreshAccessToken,
    setAccessToken,
  };
})(window);
