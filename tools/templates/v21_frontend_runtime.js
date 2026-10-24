    const LOCAL_TEST = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname)
      && /^https?:$/.test(location.protocol);
    let localTestReady = false;
    let localDeadlineMs = null;
    let testUsageCatalogue = {};

    function testBrowserTimeout() {
      let value = window.MYTECH_TEST_CONFIG?.requestTimeoutMs;
      try { value ??= new URLSearchParams(location.search || "").get("timeout_ms"); } catch {}
      const number = Number(value);
      return value !== null && value !== undefined && Number.isInteger(number) && number >= 5000 && number <= 300000
        ? number : TEST_DEFAULT_TIMEOUT_MS;
    }
    function testDeadlineMs() { return localDeadlineMs || CONFIG.requestTimeoutMs; }
    function testConnectionAvailable() { return LOCAL_TEST ? localTestReady : HOSTED || Boolean(apiKey); }
    function testNow() { return typeof performance !== "undefined" ? performance.now() : Date.now(); }
    function emitTestTiming(phase, startedAt, status) {
      const detail = { phase, durationMs: Math.max(0, Math.round(testNow() - startedAt)), status };
      if (typeof window.dispatchEvent === "function" && typeof CustomEvent !== "undefined") {
        window.dispatchEvent(new CustomEvent("mytech:test-timing", { detail }));
      }
    }
    async function configureLocalTest() {
      if (!LOCAL_TEST) return;
      const response = await fetch("/api/test/config", { cache: "no-store" });
      const config = await response.json();
      if (!response.ok || config.catalogueVersion !== "2.1-TEST" || config.productCount !== TEST_CATALOGUE_CONTRACT.count
        || !Number.isInteger(config.requestTimeoutMs) || config.requestTimeoutMs < 5000 || config.requestTimeoutMs > 300000) {
        throw new Error("INVALID_TEST_SERVER_CONFIG");
      }
      localTestReady = config.configured === true;
      localDeadlineMs = config.requestTimeoutMs + 5000;
    }
