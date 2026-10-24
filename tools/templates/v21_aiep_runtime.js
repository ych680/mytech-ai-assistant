    let testUsageCatalogue = {};
    function testBrowserTimeout() { return TEST_DEFAULT_TIMEOUT_MS; }
    function testDeadlineMs() { return CONFIG.requestTimeoutMs; }
    function testConnectionAvailable() { return HOSTED; }
    function testNow() { return typeof performance !== "undefined" ? performance.now() : Date.now(); }
    function emitTestTiming(phase, startedAt, status) {
      const detail = { phase, durationMs: Math.max(0, Math.round(testNow() - startedAt)), status };
      if (typeof window.dispatchEvent === "function" && typeof CustomEvent !== "undefined") {
        window.dispatchEvent(new CustomEvent("mytech:test-timing", { detail }));
      }
    }
