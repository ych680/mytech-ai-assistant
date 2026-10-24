    // The AIEP project connection selects the application on the server.
    // The route alone cannot prove which published workflow the project uses.
    const HOSTED = location.protocol === "https:"
      && /^project-(cmi|emi|demo)-\d{2}\.aidcec-ai-agent\.com$/i.test(location.hostname);

    function endpoint(path) {
      if (!HOSTED || path !== "/fastgpt/v1/chat/completions") throw new Error("AIEP_HOST_REQUIRED");
      return path;
    }

    function headers() { return { "content-type": "application/json" }; }
