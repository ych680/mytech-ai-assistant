"""Prepare isolated, strict-v1 evaluation resources; never write source files.

Use ``with prepare_fixture("FD") as fixture: ...``. Each instance owns a fresh
TemporaryDirectory, removed even if its consumer raises. FD is canonical JSON;
F0 and the unmodified FK bytes retain the checkout's original line endings.
Only trusted repository paths are read. No model arguments select source paths.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from tools import build_knowledge, tool3_executor, validate_products


FIXTURE_IDS = frozenset({"F0", "FD", "FK"})
DATASET_SOURCE = validate_products.DEFAULT_DATASET
KNOWLEDGE_SOURCE = tool3_executor.DEFAULT_KNOWLEDGE


class FixtureError(ValueError):
    """A source precondition or resource-integrity check failed."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FixtureError("Dataset contains duplicate JSON keys")
        result[key] = value
    return result


def _dataset(payload):
    def reject_constant(value):
        raise FixtureError("Non-standard JSON constants are forbidden")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise FixtureError("Non-finite JSON numbers are forbidden")
        return number

    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=reject_constant, parse_float=finite_float)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise FixtureError("Expected a valid UTF-8 dataset object") from error


def _invalid_dataset(payload):
    dataset = _dataset(payload)
    if type(dataset) is not dict or type(dataset.get("products")) is not list:
        raise FixtureError("Expected a dataset with product records")
    matches = [p for p in dataset["products"] if type(p) is dict and p.get("id") == "LAP-001"]
    if len(matches) != 1:
        raise FixtureError("FD requires one unique LAP-001 product")
    target = matches[0]
    if type(target.get("price_rmb")) is not int or target["price_rmb"] != 5799:
        raise FixtureError("FD requires LAP-001 price_rmb to be integer 5799")
    target["price_rmb"] = False
    try:
        return (json.dumps(dataset, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, UnicodeError) as error:
        raise FixtureError("Dataset cannot be serialized deterministically") from error


def _inconsistent_knowledge(payload):
    # Byte offsets preserve every byte outside the selected price's four digits.
    heading = "## Product Record: LAP-001 — ".encode("utf-8")
    targets = list(re.finditer(rb"(?m)^" + re.escape(heading) + rb"[^\r\n]+\r?$", payload))
    ids = list(re.finditer(rb"(?m)^Product ID: LAP-001\r?$", payload))
    if len(targets) != 1 or len(ids) != 1:
        raise FixtureError("FK requires one unique LAP-001 heading and Product ID")
    start = targets[0].end()
    following = re.search(rb"(?m)^## Product Record: ", payload[start:])
    end = start + following.start() if following else len(payload)
    record = payload[start:end]
    if not start <= ids[0].start() < end:
        raise FixtureError("FK requires Product ID inside the selected LAP-001 record")
    prices = list(re.finditer(rb"(?m)^Reference Price: [^\r\n]*\r?$", record))
    match = re.search(rb"(?m)^Reference Price: RMB (5799)(?=\r?$)", record)
    if len(prices) != 1 or match is None:
        raise FixtureError("FK requires one exact Reference Price: RMB 5799 in LAP-001")
    left, right = start + match.start(1), start + match.end(1)
    return payload[:left] + b"5800" + payload[right:]


@dataclass(frozen=True)
class PreparedFixture:
    fixture_id: str
    bindings: tool3_executor.ResourceBindings
    dataset_sha256: str
    knowledge_sha256: str
    source_dataset_sha256: str
    source_knowledge_sha256: str

    def assert_integrity(self):
        """Verify prepared bytes still match their recorded hashes."""
        try:
            actual = (sha256(self.bindings.dataset_path.read_bytes()).hexdigest(),
                      sha256(self.bindings.knowledge_path.read_bytes()).hexdigest())
        except OSError as error:
            raise FixtureError("Prepared fixture resources are unavailable") from error
        if actual != (self.dataset_sha256, self.knowledge_sha256):
            raise FixtureError("Prepared fixture resources changed")


@contextmanager
def prepare_fixture(fixture_id):
    """Copy approved sources into temporary files and yield their identity/hashes.

    Reject source drift before creating a temporary directory. Strict-v1 remains
    enabled even for FD's intentionally invalid value. The exit check detects
    consumer edits to prepared resources and concurrent edits to the sources;
    it reports them without attempting to restore or overwrite any file.
    """
    if type(fixture_id) is not str or fixture_id not in FIXTURE_IDS:
        raise FixtureError("Unknown fixture identifier")
    try:
        dataset_bytes = DATASET_SOURCE.read_bytes()
        knowledge_bytes = KNOWLEDGE_SOURCE.read_bytes()
    except OSError as error:
        raise FixtureError("Approved repository resources are unavailable") from error
    dataset = _dataset(dataset_bytes)
    try:
        if validate_products.validate_dataset(dataset, strict_v1=True):
            raise FixtureError("Baseline dataset must pass strict-v1 validation")
        if build_knowledge.check_knowledge(dataset, knowledge_bytes.decode("utf-8")):
            raise FixtureError("Baseline knowledge must be consistent with the dataset")
    except (UnicodeError, RecursionError) as error:
        raise FixtureError("Baseline resource format is unsupported") from error

    prepared_dataset = _invalid_dataset(dataset_bytes) if fixture_id == "FD" else dataset_bytes
    prepared_knowledge = _inconsistent_knowledge(knowledge_bytes) if fixture_id == "FK" else knowledge_bytes
    source_hashes = (sha256(dataset_bytes).hexdigest(), sha256(knowledge_bytes).hexdigest())
    with TemporaryDirectory(prefix="mytech-eval-") as directory:
        root = Path(directory)
        dataset_path, knowledge_path = root / "products.json", root / "knowledge.md"
        # Exclusive creation inside our new directory prevents accidental overwrite.
        with dataset_path.open("xb") as output:
            output.write(prepared_dataset)
        with knowledge_path.open("xb") as output:
            output.write(prepared_knowledge)
        fixture = PreparedFixture(
            fixture_id, tool3_executor.ResourceBindings(dataset_path, knowledge_path, strict_v1=True),
            sha256(prepared_dataset).hexdigest(), sha256(prepared_knowledge).hexdigest(), *source_hashes,
        )
        try:
            yield fixture
        finally:
            fixture.assert_integrity()
            try:
                unchanged = (DATASET_SOURCE.read_bytes() == dataset_bytes
                             and KNOWLEDGE_SOURCE.read_bytes() == knowledge_bytes)
            except OSError as error:
                raise FixtureError("Source resources became unavailable") from error
            if not unchanged:
                raise FixtureError("Original repository resources changed")
