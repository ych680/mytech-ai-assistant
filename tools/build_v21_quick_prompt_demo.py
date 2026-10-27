"""Deterministic offline frontend-only overlay of the checked PR #18 package."""
import argparse
from html import escape
import json
from pathlib import Path
import sys

try:
    from . import build_v21_completion_repair as completion
except ImportError:
    import build_v21_completion_repair as completion

parent, sync, aiep = completion.parent, completion.sync, completion.aiep
ROOT = sync.ROOT
OUTPUT_SUBDIR = Path("generated/v21_quick_prompt_demo")
SOURCE = ROOT / completion.OUTPUT_SUBDIR
TEMPLATES = ROOT / "tools/templates"
CONFIG = TEMPLATES / "v21_quick_prompt_demo.json"
RUNTIME = TEMPLATES / "v21_quick_prompt_demo.js"
STYLE = TEMPLATES / "v21_quick_prompt_demo.css"
PRESERVATION = ROOT / "tests/fixtures/v21_quick_prompt_demo_preservation.json"


def render_frontend(text, config):
    start = text.index('      <div class="quick-prompts" aria-label="Starter questions">')
    end = text.index("      </div>", start) + len("      </div>")
    buttons = ['      <div class="quick-prompts" aria-label="Starter questions">']
    for item in config["starters"]:
        buttons.append('        <button class="prompt-button" type="button" data-prompt="'
                       + escape(item["prompt"], quote=True) + '">' + escape(item["label"]) + '</button>')
    text = text[:start] + "\n".join(buttons + ["      </div>"]) + text[end:]
    text = sync.replace_once(text, "</head>", '  <style data-quick-prompt-demo>\n' + STYLE.read_text(encoding="utf-8") + "  </style>\n</head>")
    marker = '    inputElement.addEventListener("input", () => {'
    runtime = "    const DEMO_PROMPTS = " + sync.script_json(config) + ";\n" + RUNTIME.read_text(encoding="utf-8") + "\n"
    text = sync.replace_once(text, marker, runtime + marker)
    text = sync.replace_once(text, '        usageClarificationNeeded: usageIssue,',
                             '        demoUsageOwnershipAmbiguous: testUsageOwnershipAmbiguous,\n        usageClarificationNeeded: usageIssue,')
    text = sync.replace_once(text, '      if (guard.usageClarificationNeeded) throw new Error("USAGE_CLARIFICATION_REQUIRED");',
                             '      if ((guard.usageClarificationNeeded || demoHasMissingInformation(guard))\n'
                             '        && !demoMissingFieldClarification(output, guard)) {\n'
                             '        throw new Error(guard.usageClarificationNeeded ? "USAGE_CLARIFICATION_REQUIRED" : "MODEL_OUTPUT_VALIDATION_FAILED");\n'
                             '      }')
    text = sync.replace_once(text, '      invalidateRecovery();\n      addUserMessage(text);',
                             '      invalidateRecovery();\n      demoInvalidateFollowup();\n      addUserMessage(text);')
    text = sync.replace_once(text, '        updateContextAfterResponse(response);',
                             '        updateContextAfterResponse(response);\n        demoShowFollowup(response, guard, currentRequest);')
    text = sync.replace_once(text, '    function resetConversation() {\n      invalidateRecovery();',
                             '    function resetConversation() {\n      invalidateRecovery();\n      demoInvalidateFollowup();\n      testUsageOwnershipAmbiguous = false;')
    text = sync.replace_once(text, '      if (datasetReady) inputElement.focus({ preventScroll: true });',
                             '      demoResetExamples();\n      if (datasetReady) inputElement.focus({ preventScroll: true });')
    text = sync.replace_once(text, '      promptButtons.forEach((button) => {\n        button.disabled = value;\n      });',
                             '      promptButtons.forEach((button) => {\n        button.disabled = value;\n      });\n      demoRefreshControls();')
    text = sync.replace_once(text, marker + '\n      autoResizeInput();\n      refreshRecoveryAvailability();',
                             marker + '\n      autoResizeInput();\n      refreshRecoveryAvailability();\n      demoRefreshControls();')
    return text


def render_outputs():
    # Review fingerprints freeze historical packages, including every PR18 byte.
    preservation = json.loads(PRESERVATION.read_text(encoding="utf-8"))
    for name, expected in preservation["sha256"].items():
        path = ROOT / name
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("Symlink in protected baseline")
        if parent.digest(path.read_bytes()) != expected:
            raise ValueError("Protected baseline differs: " + name)
    previous = completion.render_outputs()
    if parent.check_outputs(previous, SOURCE):
        raise ValueError("PR18 package is stale; review before deriving demo candidate")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if len(config["starters"]) != 4 or len(config["examples"]) != 2 or len(config["actions"]) != 3:
        raise ValueError("Unexpected demo configuration")
    outputs = {name: raw for name, raw in previous.items() if name not in ("manifest.json", "local/manifest.json")}
    for name in ("local/index.html", "aiep/site/index.html"):
        outputs[name] = render_frontend(previous[name].decode("utf-8"), config).encode("utf-8")
    local = {"product_count": 54, "completion_validation": True, "quick_prompt_demo": True,
             "release_scope": "OFFLINE QUICK PROMPT DEMO CANDIDATE — not deployed",
             "outputs": {name.removeprefix("local/"): parent.digest(raw) for name, raw in outputs.items() if name.startswith("local/")}}
    outputs["local/manifest.json"] = sync.json_text(local).encode("utf-8")
    sources = [Path(__file__), CONFIG, RUNTIME, STYLE, PRESERVATION, SOURCE / "manifest.json"]
    manifest = {"status": "OFFLINE_ONLY_REVIEW_REQUIRED", "base_commit": "e50dbfe025f102644355ec7d0d1ff38370af19e7",
                "source_package": completion.OUTPUT_SUBDIR.as_posix(), "frontend_only": True,
                "default_deployment_changed": False, "requests_executed_by_builder": 0,
                "workflow_catalogue_knowledge": "Byte-identical to PR18", "published_revision": None,
                "kb_binding": "Unverified; unchanged from PR18",
                "sources_sha256": {p.relative_to(ROOT).as_posix(): parent.digest(p.read_bytes()) for p in sources},
                "outputs": {name: parent.digest(raw) for name, raw in outputs.items()}}
    outputs["manifest.json"] = sync.json_text(manifest).encode("utf-8")
    for name, raw in outputs.items():
        text = raw.decode("utf-8")
        if aiep.scan_credentials(text) or (name.endswith(".json") and parent.sensitive_paths(json.loads(text))):
            raise ValueError("Public demo credential check failed; values withheld")
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        outputs = render_outputs()
        directory = args.output_root.resolve() / OUTPUT_SUBDIR
        if args.check:
            if parent.check_outputs(outputs, directory):
                raise ValueError("Stale quick prompt demo candidate")
        else:
            parent.write_outputs(outputs, directory)
        print("Quick prompt demo consistent" if args.check else "Offline quick prompt demo prepared; no live calls")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Quick prompt demo failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
