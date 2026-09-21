import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cleanup_rules import Rule, classify_row, matching_rule, metadata_usernames

class RulesTests(unittest.TestCase):
    def row(self, q="alice", d="alice", site="Example", metadata=""):
        return {"query_username": q, "detected_username": d, "site": site, "metadata": metadata}

    def test_exact_rule_overrides_global_keep(self):
        action, _ = classify_row(self.row(site="GitHub"), rules=[Rule("alice","GitHub","false-positive")], keep_sites=["GitHub"], ignore_sites=[])
        self.assertEqual(action, "false-positive")

    def test_more_specific_rule_wins(self):
        rules=[Rule("*","GitLab","keep"), Rule("bob","GitLab","false-positive")]
        self.assertEqual(matching_rule(rules,"bob","GitLab").action, "false-positive")

    def test_username_mismatch_is_false_positive(self):
        action, _ = classify_row(self.row(q="alice", d="other"), rules=[], keep_sites=[], ignore_sites=[])
        self.assertEqual(action, "false-positive")

    def test_metadata_username_mismatch_is_false_positive(self):
        action, reason = classify_row(
            self.row(q="alice", d="alice", metadata="uid=1; username=bob; reputation=0"),
            rules=[], keep_sites=[], ignore_sites=[]
        )
        self.assertEqual(action, "false-positive")
        self.assertIn("bob", reason)

    def test_metadata_username_same_is_not_conflict(self):
        action, _ = classify_row(
            self.row(q="alice", d="alice", metadata="username=Alice; uid=1"),
            rules=[], keep_sites=[], ignore_sites=[]
        )
        self.assertEqual(action, "review")

    def test_metadata_usernames(self):
        self.assertEqual(
            metadata_usernames("username=a; gravatar_username=b; uid=1"),
            {"a", "b"},
        )

    def test_closed_status(self):
        action, _ = classify_row(self.row(metadata="status=closed; foo=bar"), rules=[], keep_sites=[], ignore_sites=[])
        self.assertEqual(action, "deleted")

    def test_default_review(self):
        action, _ = classify_row(self.row(), rules=[], keep_sites=[], ignore_sites=[])
        self.assertEqual(action, "review")

if __name__ == "__main__":
    unittest.main()
