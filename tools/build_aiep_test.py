"""Build a separate hosted-only AIEP TEST upload, offline and without credentials.

No FastGPT workflow is copied, imported or rewritten by this builder.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

try:
    from . import sync_catalogue as sync
except ImportError:
    import sync_catalogue as sync


OUTPUT_SUBDIR = Path("generated/aiep_v2_1_test")
RUNTIME = sync.ROOT / "tools/templates/v21_aiep_runtime.js"
TRANSPORT = sync.ROOT / "tools/templates/v21_aiep_transport.js"


def scan_credentials(text):
    """Return rule names/line numbers only; never return matched values.

    Only public candidate sources are scanned. Environment files are never read.
    This is a bounded accidental-embedding check, not a proof of all secret types.
    """
    rules = {
        "provider-token": r"\b(?:openapi-|sk-|tp-live-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}",
        "private-key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "literal-credential": r'''(?i)(?:api[_-]?key|access[_-]?token|secret|password|authorization)["']?\s*[=:]\s*["'][^"'\r\n]{8,}["']''',
        "url-credential": r"https?://[^\s/\"'<>]+:[^\s/\"'<>]+@",
        "aws-access-key": r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
        "jwt": r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    }
    return [(name, text.count("\n", 0, match.start()) + 1)
            for name, pattern in rules.items() for match in re.finditer(pattern, text)]


def render_aiep_frontend(dataset):
    errors = sync.validate_dataset(dataset, test_v21=True)
    if errors:
        raise ValueError("\n".join(errors))
    text = sync.render_frontend(dataset)
    text = sync.replace_once(text, sync.FRONTEND_RUNTIME.read_text(encoding="utf-8"), RUNTIME.read_text(encoding="utf-8"))
    start = text.index("    // Official INT6137 routing")
    end = text.index("    const CONFIG =", start)
    text = text[:start] + TRANSPORT.read_text(encoding="utf-8") + "\n" + text[end:]
    start = text.index('    <section id="key-panel"')
    end = text.index('    <div class="messages"', start)
    text = text[:start] + text[end:]
    start = text.index("    function readRememberedKey()")
    end = text.index("    async function initialize()", start)
    text = text[:start] + text[end:]
    text = sync.replace_once(text, "        await configureLocalTest();\n        initializeKeyPanel();\n", "")
    text = sync.replace_once(text, "body: JSON.stringify(LOCAL_TEST ? payload : {", "body: JSON.stringify({")
    text = sync.replace_once(text, '          stream: false,', '          stream: false,\n          detail: false,')
    text = sync.replace_once(text, '      if (!testConnectionAvailable()) throw new Error("KEY_REQUIRED");',
                             '      if (!testConnectionAvailable()) throw new Error("AIEP_HOST_REQUIRED");')
    text = sync.replace_once(text, '      else if (!testConnectionAvailable()) setStatus("unavailable", LOCAL_TEST ? "Configure the separate TEST server connection" : "FastGPT TEST Key Required");',
                             '      else if (!testConnectionAvailable()) setStatus("unavailable", "Open the separate AIEP TEST site to connect");')
    text = sync.replace_once(text, '      else setStatus("ready", HOSTED ? "AIEP / Ready to Connect" : "Key Set / Ready to Connect");',
                             '      else setStatus("ready", "AIEP TEST / Ready to Connect");')
    text = sync.replace_once(text, '      if (status === 401) message = HOSTED ? "Please reload the page and sign in again." : "That key was not accepted. Check your FastGPT application key.";',
                             '      if (status === 401) message = "Please reload the page and sign in again.";')
    text = sync.replace_once(text, '      else if (status === 403) message = HOSTED ? "This chatbot is paused right now." : "This key cannot use that feature.";',
                             '      else if (status === 403) message = "This chatbot is paused right now.";')
    text = sync.replace_once(text, '      else if (error.message === "KEY_REQUIRED") message = "Enter your own FastGPT application key to continue.";',
                             '      else if (error.message === "AIEP_HOST_REQUIRED") message = "Open the separate AIEP TEST site to connect.";')
    text = sync.replace_once(text, 'required: ["category", "recommended_product", "price", "reason"],',
                             'required: ["category", "recommended_product", "price", "reason", "source"],')
    # Match legacy fetch mode/credential defaults: AIEP may give this document
    # an opaque origin. Forcing same-origin mode would reject its proxy request.
    # CORS/preflight and sandbox authentication still require platform support.
    # Keep rejecting redirects instead of following the proxy to another service.
    text = sync.replace_once(text, '        method: "POST",', '        method: "POST",\n        redirect: "error",')
    for forbidden in ("LOCAL_TEST", "apiKey", "localStorage", "/api/test/", "localhost", "127.0.0.1", "authorization", "Bearer ", "FASTGPT_BASE", 'id="key-panel"'):
        if forbidden in text:
            raise ValueError("Unexpected local or credential runtime in AIEP candidate")
    findings = scan_credentials(text)
    if findings:
        raise ValueError(f"Credential review failed (rule, line): {findings}")
    if len(text.encode("utf-8")) >= 2_000_000:
        raise ValueError("AIEP single-file upload exceeds the reviewed size limit")
    return text


def render_outputs(dataset):
    page = render_aiep_frontend(dataset).encode("utf-8")
    manifest = {
        "release_scope": "Separate AIEP v2.1 TEST candidate; review required before upload",
        "upload_directory": str(OUTPUT_SUBDIR / "site"),
        "upload_files": ["index.html"],
        "master": str(sync.TEST_DATASET.relative_to(sync.ROOT)),
        "master_sha256": hashlib.sha256(sync.json_text(dataset).encode("utf-8")).hexdigest(),
        "product_count": len(dataset["products"]),
        "supported_categories": dataset["supported_categories"],
        "transport": {"route": "/fastgpt/v1/chat/completions", "authentication": "AIEP server-side project connection only",
                      "application_selection": "Configured project credential; no browser appId/model",
                      "binding_status": "UNVERIFIED — operator must confirm separate project maps to published v2.1 TEST",
                      "published_workflow_policy": "Keep currently published TEST unchanged; do not import generated shortened prompts"},
        "sources_sha256": {str(path.relative_to(sync.ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in (sync.FRONTEND, sync.ROOT / "tools/sync_catalogue.py", Path(__file__),
                                        sync.FRONTEND_VALIDATOR, sync.USAGE_VALIDATOR, sync.USAGE_COMPATIBILITY,
                                        sync.TEST_SETTINGS, sync.CITATION_HELPERS, RUNTIME, TRANSPORT)},
        "credential_scan": "PASS: public candidate only; no environment files read; heuristic rules in tools/build_aiep_test.py",
        "outputs": {"site/index.html": hashlib.sha256(page).hexdigest()},
    }
    return {"site/index.html": page, "manifest.json": sync.json_text(manifest).encode("utf-8")}


def check_outputs(outputs, directory):
    errors = sync.check_outputs(outputs, directory)
    site = directory / "site"
    if any(path.is_symlink() for path in (directory.parent, directory, site, *(directory / name for name in outputs))):
        errors.append(f"{directory}: symlink in AIEP upload output")
    if site.exists() and sorted(path.name for path in site.iterdir()) != ["index.html"]:
        errors.append(f"{site}: upload must contain only index.html")
    return errors


def write_outputs(outputs, directory):
    for path in (directory.parent, directory, directory / "site", *(directory / name for name in outputs)):
        if path.is_symlink():
            raise ValueError("Refusing symlink AIEP output path")
    if (directory / "site").exists() and sorted(path.name for path in (directory / "site").iterdir()) != ["index.html"]:
        raise ValueError("Unexpected AIEP upload contents; review and remove extra files manually")
    (directory / "site").mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        path = directory / name
        if not path.exists() or path.read_bytes() != payload:
            path.write_bytes(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=sync.TEST_DATASET)
    parser.add_argument("--output-root", type=Path, default=sync.ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        outputs = render_outputs(sync.load_dataset(args.dataset))
        directory = args.output_root.resolve() / OUTPUT_SUBDIR
        if args.check:
            errors = check_outputs(outputs, directory)
            if errors:
                raise ValueError("\n".join(errors))
        else:
            write_outputs(outputs, directory)
        print(f"AIEP TEST {'consistent' if args.check else 'prepared'}: {directory / 'site'} (single upload file).")
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
