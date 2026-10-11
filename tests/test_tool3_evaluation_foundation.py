"""Contract/fixture tests only: no evaluation runner, model, or credentials."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluations import fixtures
from evaluations import scenario_contract as contract
from tools import build_knowledge, validate_products


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.network_guards = []
        for target in ("socket.create_connection", "socket.socket.connect",
                       "urllib.request.OpenerDirector.open", "tools.tool3_tokenproxy.http_transport"):
            guard = patch(target, side_effect=AssertionError("Network forbidden in foundation tests"))
            self.network_guards.append(guard.start())
            self.addCleanup(guard.stop)

    def tearDown(self):
        for guard in self.network_guards:
            guard.assert_not_called()


class ScenarioContractTests(OfflineTests):
    def setUp(self):
        super().setUp()
        self.manifest = contract.load_manifest()

    def reject(self, mutate):
        candidate = deepcopy(self.manifest)
        mutate(candidate)
        with self.assertRaises(contract.ManifestError):
            contract.validate_manifest(candidate)

    def test_loads_all_sixteen_versioned_scenarios_without_execution(self):
        before = deepcopy(self.manifest)
        with patch.object(fixtures, "prepare_fixture") as prepare, \
             patch("tools.tool3_tokenproxy.orchestrate") as orchestrate:
            result = contract.validate_manifest(self.manifest)
        prepare.assert_not_called()
        orchestrate.assert_not_called()
        self.assertEqual(self.manifest, before)
        self.assertEqual(result["schema_version"], "1.0.0")
        self.assertEqual([s["id"] for s in result["scenarios"]],
                         [f"AE-{number:02d}" for number in range(1, 17)])

    def test_rejects_duplicate_missing_and_unknown_scenario_ids(self):
        self.reject(lambda m: m["scenarios"].append(deepcopy(m["scenarios"][0])))
        self.reject(lambda m: m["scenarios"].pop())
        self.reject(lambda m: m["scenarios"][0].update(id="AE-17"))

    def test_validates_schema_manifest_and_scenario_versions(self):
        self.reject(lambda m: m.update(schema_version="2.0.0"))
        for invalid in ("1", "1.0", "01.0.0", "1.0.0-beta", "", 1, None, [], "1.0.-1"):
            with self.subTest(version=invalid):
                self.reject(lambda m: m.update(manifest_version=invalid))
                self.reject(lambda m: m["scenarios"][0].update(version=invalid))
        updated = deepcopy(self.manifest)
        updated["manifest_version"] = "1.2.3"
        updated["scenarios"][0]["version"] = "2.0.1"
        contract.validate_manifest(updated)

    def test_rejects_unknown_and_missing_fields_at_every_object_level(self):
        paths = (
            (), ("scenarios", 0), ("scenarios", 0, "script", 0),
            ("scenarios", 0, "script", 0, "calls", 0),
            ("scenarios", 0, "script", 0, "calls", 0, "arguments"),
            ("scenarios", 0, "required_operations", 0),
            ("scenarios", 0, "required_operations", 0, "acceptable_results", 0),
            ("scenarios", 0, "acceptable_plans", 0),
            ("scenarios", 0, "expected"), ("scenarios", 0, "expected", "orchestration"),
            ("scenarios", 0, "expected", "tool_results", 0),
            ("scenarios", 0, "expected", "operation_handling", 0),
            ("scenarios", 0, "human_review"),
        )
        for path in paths:
            for mode in ("unknown", "missing"):
                with self.subTest(path=path, mode=mode):
                    candidate = deepcopy(self.manifest)
                    value = candidate
                    for key in path:
                        value = value[key]
                    if mode == "unknown":
                        value["executable_code"] = "forbidden"
                    else:
                        del value[next(iter(value))]
                    with self.assertRaises(contract.ManifestError):
                        contract.validate_manifest(candidate)

    def test_rejects_unknown_scenario_types_fixtures_and_blank_requests(self):
        for key, values in (("scenario_type", ("live_model", "unknown", [])),
                            ("fixture_id", ("FZ", "../resources", None)),
                            ("request", ("", "  ", 123, "\ud800"))):
            for value in values:
                with self.subTest(key=key, value=value):
                    self.reject(lambda m: m["scenarios"][0].update({key: value}))

    def test_rejects_malformed_or_executable_provider_scripts(self):
        for script in ([], {}, [None], [{"type": "python", "code": "run()"}],
                       [{"type": "final", "text": ""}],
                       [{"type": "tool_calls", "calls": []}],
                       [{"type": "http_error", "status": True}],
                       [{"type": "http_error", "status": 503}],
                       [{"type": "final", "text": "Done"}, {"type": "final", "text": "Again"}]):
            with self.subTest(script=script):
                self.reject(lambda m: m["scenarios"][0].update(script=script))
        for changes in ({"id": "bad id"}, {"arguments": "{}"}, {"name": []},
                        {"arguments": {"dataset": False}}, {"arguments": {"dataset": []}}):
            with self.subTest(changes=changes):
                self.reject(lambda m: m["scenarios"][0]["script"][0]["calls"][0].update(changes))
        self.reject(lambda m: m["scenarios"][2]["script"][0]["calls"][1].update(id="v1"))

    def test_negative_selection_data_requires_a_rejected_batch_oracle(self):
        self.reject(lambda m: m["scenarios"][0]["script"][0]["calls"][0].update(name="generate_knowledge"))
        self.reject(lambda m: m["scenarios"][0]["script"][0]["calls"][0]["arguments"].update(dataset="other_dataset"))
        for scenario in self.manifest["scenarios"][8:10]:
            self.assertEqual(scenario["expected"]["orchestration"]["code"], "invalid_tool_calls")
            self.assertEqual(scenario["expected"]["tool_results"], [])

    def test_both_tool_plans_allow_batch_permutation_and_sequential_alternatives(self):
        scenario = self.manifest["scenarios"][2]
        plans = scenario["acceptable_plans"]
        self.assertEqual(len(plans), 3)
        self.assertEqual(plans[0]["ordering"], "any_within_round")
        self.assertEqual(plans[1]["rounds"], [["validate_products"], ["check_knowledge"]])
        self.assertEqual(plans[2]["rounds"], [["check_knowledge"], ["validate_products"]])
        self.assertEqual(self.manifest["scenarios"][10]["acceptable_plans"], [plans[1]])
        for rounds in ([], [[]], [["validate_products"]], [["validate_products"]] * 3,
                       [["validate_products", "validate_products"]], [["generate_knowledge"]]):
            with self.subTest(rounds=rounds):
                self.reject(lambda m: m["scenarios"][2]["acceptable_plans"][0].update(rounds=rounds))

    def test_internal_validation_does_not_fabricate_an_explicit_call(self):
        knowledge = self.manifest["scenarios"][1]
        self.assertEqual([op["operation"] for op in knowledge["required_operations"]], ["knowledge_inspection"])
        self.assertEqual(knowledge["acceptable_plans"][0]["rounds"], [["check_knowledge"]])
        semantic = self.manifest["scenarios"][4]["required_operations"][0]
        self.assertEqual(semantic["operation"], "dataset_validation")
        self.assertEqual({row["name"] for row in semantic["acceptable_results"]},
                         {"validate_products", "check_knowledge"})
        self.reject(lambda m: m["scenarios"][0]["required_operations"][0]["acceptable_results"][0].update(name="check_knowledge"))

    def test_skipped_inspection_is_an_expected_block_not_completed_work(self):
        scenario = self.manifest["scenarios"][7]
        required = scenario["required_operations"][1]
        self.assertEqual(required["acceptable_results"][0]["status"], "success")
        self.assertEqual(required["acceptable_blocks"][0]["status"], "skipped")
        self.assertEqual(scenario["expected"]["operation_handling"][1]["state"], "blocked_expected")
        self.assertEqual(scenario["expected"]["task_verdict"], "pass")
        self.reject(lambda m: m["scenarios"][7]["expected"]["operation_handling"][1].update(state="met"))
        self.reject(lambda m: m["scenarios"][7]["required_operations"][1].update(
            acceptable_results=m["scenarios"][7]["required_operations"][1]["acceptable_blocks"]))

    def test_expected_failures_do_not_become_failed_evaluation_expectations(self):
        failed = {"AE-05", "AE-09", "AE-10", "AE-12", "AE-13", "AE-14", "AE-16"}
        for scenario in self.manifest["scenarios"]:
            with self.subTest(scenario=scenario["id"]):
                expected = scenario["expected"]
                self.assertEqual(expected["evaluation_expectation_verdict"], "pass")
                if scenario["id"] in failed:
                    self.assertEqual(expected["task_verdict"], "fail")
        incomplete = self.manifest["scenarios"][11]["expected"]
        self.assertEqual(incomplete["orchestration"]["execution_status"], "success")
        self.assertEqual(incomplete["task_verdict"], "fail")
        for index in (5, 6, 7):
            expected = self.manifest["scenarios"][index]["expected"]
            self.assertEqual(expected["orchestration"]["execution_status"], "failed")
            self.assertEqual(expected["task_verdict"], "pass")
        self.reject(lambda m: m["scenarios"][11]["expected"].update(task_verdict="pass"))

    def test_human_review_stays_pending_and_anticipated_labels_are_not_annotations(self):
        for index, anticipated in ((3, "pass"), (14, "fail")):
            scenario = self.manifest["scenarios"][index]
            self.assertTrue(scenario["human_review"]["required"])
            self.assertEqual(scenario["human_review"]["state"], "pending")
            self.assertEqual(scenario["human_review"]["anticipated_outcome"], anticipated)
            self.assertEqual(scenario["expected"]["task_verdict"], "pending_review")
            self.reject(lambda m: m["scenarios"][index]["human_review"].update(state="reviewed"))
            self.reject(lambda m: m["scenarios"][index]["expected"].update(task_verdict="pass"))
            self.reject(lambda m: m["scenarios"][index]["human_review"].update(annotation={"verdict": anticipated}))

    def test_rejects_conflicting_oracles_bad_counts_and_dangling_results(self):
        changes = (
            lambda m: m["scenarios"][0]["expected"]["orchestration"].update(api_requests=True),
            lambda m: m["scenarios"][0]["expected"]["orchestration"].update(api_requests=3),
            lambda m: m["scenarios"][0]["expected"]["orchestration"].update(tool_rounds=0),
            lambda m: m["scenarios"][0]["expected"]["orchestration"].update(execution_status="failed"),
            lambda m: m["scenarios"][0]["expected"]["tool_results"][0].update(tool_call_id="missing"),
            lambda m: m["scenarios"][0]["expected"]["tool_results"][0].update(code=[]),
            lambda m: m["scenarios"][0]["expected"]["tool_results"][0].update(status="skipped"),
            lambda m: m["scenarios"][0]["expected"].update(evaluation_expectation_verdict="fail"),
            lambda m: m["scenarios"][0]["expected"].update(reason_codes=["invented"]),
            lambda m: m["scenarios"][0]["expected"]["operation_handling"][0].update(state="missing"),
        )
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.reject(change)

    def test_rejected_batches_cannot_claim_execution_and_limits_need_a_real_bound(self):
        candidate = deepcopy(self.manifest)
        rejected = candidate["scenarios"][8]["expected"]
        rejected["tool_results"] = deepcopy(candidate["scenarios"][0]["expected"]["tool_results"])
        rejected["orchestration"].update(execution_status="success", tool_rounds=1)
        rejected["operation_handling"][0]["state"] = "met"
        with self.assertRaisesRegex(contract.ManifestError, "exclude rejected calls"):
            contract.validate_manifest(candidate)
        candidate = deepcopy(self.manifest)
        limited = candidate["scenarios"][15]
        limited["script"] = [limited["script"][0]]
        limited["expected"]["orchestration"].update(api_requests=1, tool_rounds=0, execution_status="not_run")
        limited["expected"]["tool_results"] = []
        for row in limited["expected"]["operation_handling"]:
            row["state"] = "missing"
        with self.assertRaisesRegex(contract.ManifestError, "beyond"):
            contract.validate_manifest(candidate)

    def test_json_loader_rejects_duplicate_keys_invalid_encoding_and_nonfinite_constants(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            for payload in (b'{"schema_version":"1.0.0","schema_version":"1.0.0"}',
                            b'{"scenarios":[{"id":"AE-01","id":"AE-01"}]}',
                            b'{"x":NaN}', b"{", b"\xff"):
                with self.subTest(payload=payload):
                    path.write_bytes(payload)
                    with self.assertRaises(contract.ManifestError):
                        contract.load_manifest(path)
            path.unlink()
            with self.assertRaises(contract.ManifestError):
                contract.load_manifest(path)


class FixtureFoundationTests(OfflineTests):
    @classmethod
    def setUpClass(cls):
        cls.dataset_bytes = fixtures.DATASET_SOURCE.read_bytes()
        cls.knowledge_bytes = fixtures.KNOWLEDGE_SOURCE.read_bytes()
        cls.catalogue = json.loads(cls.dataset_bytes)

    def tearDown(self):
        self.assertEqual(fixtures.DATASET_SOURCE.read_bytes(), self.dataset_bytes)
        self.assertEqual(fixtures.KNOWLEDGE_SOURCE.read_bytes(), self.knowledge_bytes)
        super().tearDown()

    def test_baseline_is_byte_for_byte_copy_with_strict_bindings(self):
        with fixtures.prepare_fixture("F0") as fixture:
            self.assertEqual(fixture.fixture_id, "F0")
            self.assertIs(fixture.bindings.strict_v1, True)
            self.assertNotEqual(fixture.bindings.dataset_path, fixtures.DATASET_SOURCE)
            self.assertNotEqual(fixture.bindings.knowledge_path, fixtures.KNOWLEDGE_SOURCE)
            self.assertEqual(fixture.bindings.dataset_path.read_bytes(), self.dataset_bytes)
            self.assertEqual(fixture.bindings.knowledge_path.read_bytes(), self.knowledge_bytes)
            fixture.assert_integrity()

    def test_invalid_dataset_changes_only_target_value_and_has_one_expected_error(self):
        with fixtures.prepare_fixture("FD") as fixture:
            dataset = validate_products.load_dataset(fixture.bindings.dataset_path)
            expected = deepcopy(self.catalogue)
            target = next(product for product in expected["products"] if product["id"] == "LAP-001")
            target["price_rmb"] = False
            self.assertEqual(dataset, expected)
            self.assertEqual(fixture.bindings.knowledge_path.read_bytes(), self.knowledge_bytes)
            self.assertIs(fixture.bindings.strict_v1, True)
            errors = validate_products.validate_dataset(dataset, strict_v1=fixture.bindings.strict_v1)
            self.assertEqual(len(errors), 1)
            self.assertIn("price_rmb: must be a positive integer", errors[0])
            self.assertNotEqual(fixture.dataset_sha256, fixture.source_dataset_sha256)

    def test_knowledge_changes_only_target_price_and_has_one_inconsistency(self):
        with fixtures.prepare_fixture("FK") as fixture:
            changed = fixture.bindings.knowledge_path.read_bytes()
            self.assertEqual(changed, self.knowledge_bytes.replace(
                b"Reference Price: RMB 5799", b"Reference Price: RMB 5800", 1))
            self.assertEqual(fixture.bindings.dataset_path.read_bytes(), self.dataset_bytes)
            errors = build_knowledge.check_knowledge(self.catalogue, changed.decode("utf-8"))
            self.assertEqual(errors, ["records[0].Reference Price: missing or differs from dataset"])
            self.assertNotEqual(fixture.knowledge_sha256, fixture.source_knowledge_sha256)

    def test_hashes_record_exact_prepared_and_original_bytes_for_every_fixture(self):
        for identifier in ("F0", "FD", "FK"):
            with self.subTest(identifier=identifier), fixtures.prepare_fixture(identifier) as fixture:
                self.assertEqual(fixture.dataset_sha256, sha256(fixture.bindings.dataset_path.read_bytes()).hexdigest())
                self.assertEqual(fixture.knowledge_sha256, sha256(fixture.bindings.knowledge_path.read_bytes()).hexdigest())
                self.assertEqual(fixture.source_dataset_sha256, sha256(self.dataset_bytes).hexdigest())
                self.assertEqual(fixture.source_knowledge_sha256, sha256(self.knowledge_bytes).hexdigest())

    def test_repeated_instances_have_distinct_paths_and_identical_content_hashes(self):
        for identifier in ("F0", "FD", "FK"):
            with self.subTest(identifier=identifier):
                with fixtures.prepare_fixture(identifier) as first, fixtures.prepare_fixture(identifier) as second:
                    paths = (first.bindings.dataset_path.parent, second.bindings.dataset_path.parent)
                    self.assertNotEqual(*paths)
                    self.assertEqual(first.dataset_sha256, second.dataset_sha256)
                    self.assertEqual(first.knowledge_sha256, second.knowledge_sha256)
                self.assertTrue(all(not path.exists() for path in paths))

    def test_temporary_directory_is_removed_when_consumer_raises(self):
        with self.assertRaisesRegex(RuntimeError, "consumer failure"):
            with fixtures.prepare_fixture("F0") as fixture:
                root = fixture.bindings.dataset_path.parent
                raise RuntimeError("consumer failure")
        self.assertFalse(root.exists())

    def test_temporary_directory_is_removed_when_preparation_fails(self):
        roots = []
        temporary_directory = tempfile.TemporaryDirectory

        def temporary(**kwargs):
            directory = temporary_directory(**kwargs)
            roots.append(Path(directory.name))
            return directory

        with patch.object(fixtures, "TemporaryDirectory", side_effect=temporary), \
             patch.object(fixtures, "PreparedFixture", side_effect=RuntimeError("setup failed")), \
             self.assertRaisesRegex(RuntimeError, "setup failed"):
            with fixtures.prepare_fixture("F0"):
                self.fail("Preparation must fail before yielding")
        self.assertEqual(len(roots), 1)
        self.assertFalse(roots[0].exists())

    def test_integrity_failure_is_explicit_and_still_cleans_temporary_files(self):
        for action in ("change", "remove"):
            with self.subTest(action=action), self.assertRaises(fixtures.FixtureError):
                with fixtures.prepare_fixture("F0") as fixture:
                    root = fixture.bindings.dataset_path.parent
                    if action == "change":
                        fixture.bindings.dataset_path.write_bytes(b"changed")
                    else:
                        fixture.bindings.knowledge_path.unlink()
            self.assertFalse(root.exists())

    def test_unknown_fixture_fails_before_source_access_or_directory_creation(self):
        with patch.object(Path, "read_bytes") as read, patch.object(fixtures, "TemporaryDirectory") as temporary:
            for identifier in ("FZ", "../F0", None, [], 0):
                with self.subTest(identifier=identifier), self.assertRaises(fixtures.FixtureError):
                    with fixtures.prepare_fixture(identifier):
                        self.fail("Unknown fixture must not yield")
            read.assert_not_called()
            temporary.assert_not_called()

    def test_invalid_dataset_requires_unique_target_and_exact_original_price(self):
        candidates = []
        missing = deepcopy(self.catalogue)
        missing["products"] = [p for p in missing["products"] if p["id"] != "LAP-001"]
        candidates.append(missing)
        duplicate = deepcopy(self.catalogue)
        duplicate["products"].append(deepcopy(duplicate["products"][0]))
        candidates.append(duplicate)
        for value in (5800, False, 5799.0):
            changed = deepcopy(self.catalogue)
            changed["products"][0]["price_rmb"] = value
            candidates.append(changed)
        for candidate in candidates:
            with self.subTest(candidate=candidates.index(candidate)), self.assertRaises(fixtures.FixtureError):
                fixtures._invalid_dataset(json.dumps(candidate).encode("utf-8"))
        for payload in (b"{", b"\xff", b'{"products":[],"products":[]}',
                        b'{"extra":NaN}', b'{"extra":1e400}'):
            with self.subTest(payload=payload), self.assertRaises(fixtures.FixtureError):
                fixtures._invalid_dataset(payload)

    def test_knowledge_mutation_requires_exact_unique_target_within_selected_record(self):
        source = self.knowledge_bytes
        heading = next(line for line in source.splitlines() if line.startswith(b"## Product Record: LAP-001"))
        candidates = (
            source.replace(b"LAP-001", b"LAP-999"),
            source + b"\n" + heading + b"\nProduct ID: LAP-001\nReference Price: RMB 5799\n",
            source.replace(b"Reference Price: RMB 5799", b"Reference Price: RMB 5800", 1),
            source.replace(b"Reference Price: RMB 5799", b"Reference Price: RMB 5799\nReference Price: RMB 5799", 1),
            source.replace(b"Reference Price: RMB 5799", b"Reference Price: RMB 5799\nReference Price: RMB 1", 1),
            source.replace(b"Product ID: LAP-001", b"Product ID: LAP-002", 1),
        )
        for index, candidate in enumerate(candidates):
            with self.subTest(candidate=index), self.assertRaises(fixtures.FixtureError):
                fixtures._inconsistent_knowledge(candidate)

    def test_knowledge_mutation_preserves_lf_and_crlf_content_exactly(self):
        lf = self.knowledge_bytes.replace(b"\r\n", b"\n")
        for payload in (lf, lf.replace(b"\n", b"\r\n")):
            with self.subTest(crlf=b"\r\n" in payload):
                self.assertEqual(fixtures._inconsistent_knowledge(payload), payload.replace(
                    b"Reference Price: RMB 5799", b"Reference Price: RMB 5800", 1))

    def test_source_drift_is_rejected_without_creating_a_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset, knowledge = Path(directory) / "source.json", Path(directory) / "source.md"
            dataset.write_bytes(self.dataset_bytes)
            knowledge.write_bytes(self.knowledge_bytes)
            for corrupt in ("dataset", "knowledge"):
                dataset.write_bytes(b"{}" if corrupt == "dataset" else self.dataset_bytes)
                knowledge.write_bytes(b"# drift\n" if corrupt == "knowledge" else self.knowledge_bytes)
                before = (dataset.read_bytes(), knowledge.read_bytes())
                with self.subTest(corrupt=corrupt), \
                     patch.object(fixtures, "DATASET_SOURCE", dataset), \
                     patch.object(fixtures, "KNOWLEDGE_SOURCE", knowledge), \
                     patch.object(fixtures, "TemporaryDirectory") as temporary, \
                     self.assertRaises(fixtures.FixtureError):
                    with fixtures.prepare_fixture("F0"):
                        self.fail("Drift must fail before yielding")
                temporary.assert_not_called()
                self.assertEqual((dataset.read_bytes(), knowledge.read_bytes()), before)


if __name__ == "__main__":
    unittest.main()
