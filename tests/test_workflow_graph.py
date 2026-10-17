"""Offline routing checks against the portable FastGPT workflow export."""

import json
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / "workflow" / "mytech-fastgpt-workflow.json"
ROUTER_ID = "y641hB3ildC7AsuP"
EXPECTED_ROUTES = {
    "supported": ("ez6SYCKnzlr5MQt3", "tVqEyTvHnHG9GG1D", "Conversation State Update"),
    "unsupported": ("oZIEJGxWNeVYLAAs", "tkCKIXzj7te874Od", "Unsupported Category Response"),
    "help": ("a7qMok3Xm40sFqSJ", "cLOxjUrmsZO4aToG", "Help & Greeting Response"),
    "ELSE": ("ELSE", "irfKAbR8EsvBDRZ4", "Unrelated Request Response"),
}


class WorkflowGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        graph = json.loads(WORKFLOW.read_text(encoding="utf-8-sig"))
        cls.nodes = {node["nodeId"]: node for node in graph["nodes"]}
        cls.router = cls.nodes[ROUTER_ID]
        cls.edges = [edge for edge in graph["edges"] if edge["source"] == ROUTER_ID]

    def test_scope_condition_to_target_mappings(self):
        branches = next(item["value"] for item in self.router["inputs"]
                        if item["key"] == "ifElseList")
        self.assertEqual(len(branches), 3)
        conditions = {"ELSE": "ELSE"}
        for branch in branches:
            self.assertEqual(len(branch["list"]), 1)
            condition = branch["list"][0]
            self.assertEqual(condition["condition"], "equalTo")
            conditions[branch["branchId"]] = condition["value"]
        self.assertEqual(len(conditions), 4)
        self.assertEqual(set(conditions.values()), set(EXPECTED_ROUTES))
        self.assertEqual(len(self.edges), 4)
        actual = {}
        for edge in self.edges:
            branch_id = edge["sourceHandle"].removeprefix(f"{ROUTER_ID}-source-")
            condition = conditions[branch_id]
            self.assertNotIn(condition, actual)
            actual[condition] = self.nodes[edge["target"]]["name"]
        self.assertEqual(actual, {condition: route[2]
                                  for condition, route in EXPECTED_ROUTES.items()})

    def test_router_handles_and_reply_semantic_roles(self):
        expected_handles = {f"{ROUTER_ID}-source-{route[0]}"
                            for route in EXPECTED_ROUTES.values()}
        self.assertEqual(len(self.edges), 4)
        self.assertEqual({edge["sourceHandle"] for edge in self.edges}, expected_handles)
        for branch_id, target_id, name in EXPECTED_ROUTES.values():
            with self.subTest(branch=branch_id):
                edge = next(edge for edge in self.edges
                            if edge["sourceHandle"] == f"{ROUTER_ID}-source-{branch_id}")
                self.assertEqual(edge["target"], target_id)
                self.assertEqual(edge["targetHandle"], f"{target_id}-target-left")
                self.assertEqual(self.nodes[target_id]["name"], name)

        replies = {}
        for role in ("help", "ELSE"):
            node = self.nodes[EXPECTED_ROUTES[role][1]]
            self.assertEqual(node["flowNodeType"], "answerNode")
            response = json.loads(next(item["value"] for item in node["inputs"]
                                       if item["key"] == "text"))
            self.assertEqual(response["recommendations"], [])
            self.assertIs(response["clarification_needed"], False)
            replies[role] = response
        self.assertIn("Hi! I'm MyTech", replies["help"]["answer"])
        self.assertIn("I can help you choose", replies["help"]["answer"])
        self.assertIn("your budget in RMB", replies["help"]["answer"])
        self.assertIn("your main usage", replies["help"]["answer"])
        self.assertTrue(replies["help"]["next_step"])
        self.assertIn("only helps with electronic product recommendations",
                      replies["ELSE"]["answer"])
        self.assertEqual(replies["ELSE"]["next_step"], "")


if __name__ == "__main__":
    unittest.main()
