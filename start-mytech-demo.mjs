// Node's explicit --env-file selects the environment; this launcher loads none.
import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createTestServer, testServerConfig } from "./mytech_v2_1_test_server.mjs";

const DIRECTORY = fileURLToPath(new URL("./generated/v21_quick_prompt_demo/local/", import.meta.url));

export async function startMyTechDemo(env = process.env, options = {}) {
  const config = testServerConfig(env);
  const server = await createTestServer(config, { ...options, directory: DIRECTORY,
    onTiming: config.timings ? detail => console.log(JSON.stringify(detail)) : undefined });
  await new Promise((ready, reject) => {
    server.once("error", reject);
    server.listen(config.port, "127.0.0.1", () => {
      server.off("error", reject);
      ready();
    });
  });
  return { server, configured: config.configured };
}

function isDirectExecution() {
  if (!process.argv[1]) return false;
  try {
    // argv can retain a directory alias (e.g. macOS /var); ESM resolves it.
    return realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
  } catch {
    // Imports from stdin/eval can have a non-file argv[1].
    return false;
  }
}

if (isDirectExecution()) {
  try {
    const { server, configured } = await startMyTechDemo();
    console.log(`MyTech v2.1 Quick Prompt Demo (four-button frontend): http://127.0.0.1:${server.address().port}`);
    console.log(`TEST API binding: ${configured ? "configured" : "not configured (offline)"}. Stop with Ctrl+C.`);
  } catch (error) {
    // Fixed messages only: never print configuration, paths or upstream errors.
    if (error.code === "EADDRINUSE") {
      console.error("MYTECH_DEMO_PORT_IN_USE: MYTECH_TEST_PORT is already occupied. Stop the other server or select a free TEST port.");
    } else if (["ENOENT", "ENOTDIR", "STALE_TEST_ASSETS"].includes(error.code)) {
      console.error("MYTECH_DEMO_ASSETS_INVALID: required generated Quick Prompt Demo assets are missing or stale. Run tools/build_v21_quick_prompt_demo.py.");
    } else {
      console.error("MYTECH_DEMO_START_FAILED: check TEST environment settings and generated Quick Prompt Demo assets.");
    }
    process.exitCode = 1;
  }
}
