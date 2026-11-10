"""A PASS is withheld when any part of the sentence went unread.

Each rewording below keeps a wrong explanation's account, figures and stated cause, and
each once got PASS from the rules. The fuzz test rewrites every defective sentence in a
slice of the benchmark the same ways and requires that none of them is passed."""
import re
import unittest

from proven.report import run
from proven.synth import generate_split

SCENARIOS = generate_split("test", 60, "seen")

CONNECTORS = ("due to", "because of", "driven by", "as a result of", "reflecting",
              "attributable to", "owing to", "thanks to", "on the back of")
UNKNOWN_CONNECTORS = ("fueled by", "stemming from", "courtesy of", "following", "after",
                      "with the culprit being", "which we trace to", "explained by")
FLIPS = {"rose": "fell", "increased": "decreased", "grew": "declined", "climbed": "dropped",
         "fell": "rose", "decreased": "increased", "declined": "grew", "dropped": "climbed",
         "increase": "decrease", "decrease": "increase"}
UNKNOWN_DIRECTIONS = ("slid", "moved", "swung", "ballooned", "eased", "ticked", "came in at")


def verdict_of(scenario, original: str, rewritten: str) -> str:
    report = run(scenario.explanation.replace(original, rewritten), scenario.ledger)
    for claim in report["claims"]:
        if claim["claim"]["quote"] == rewritten:
            return claim["verdict"]
    return "MISSED"


def first(family: str):
    scenario = next(s for s in SCENARIOS if s.family == family)
    return scenario, scenario.labels[0].quote


def rewordings(quote: str):
    """Ways of saying the same wrong thing in words the readers do not know."""
    connector = next((c for c in CONNECTORS if f" {c} " in quote), None)
    if connector:
        for unknown in UNKNOWN_CONNECTORS:
            yield quote.replace(f" {connector} ", f" {unknown} ", 1)
        head, reason = quote.split(f" {connector} ", 1)
        reason = reason.rstrip(".")
        yield f"{head}; {reason} was the reason."
        yield f"{head} {connector} {reason}, not the usual run rate."
        yield f"{head} {connector} {reason} rather than anything else."
        yield f"{head} {connector} something other than {reason}."
        yield f"{head}, and {connector} {reason} it did not."
    for word in FLIPS:
        if re.search(rf"\b{word}\b", quote):
            for unknown in UNKNOWN_DIRECTIONS:
                yield re.sub(rf"\b{word}\b", unknown, quote, count=1)
            yield re.sub(rf"\b{word}\b", f"{FLIPS[word]} then {word}", quote, count=1)
    money = re.search(r"(?:approximately )?\$[\d.,]+[KM]?", quote)
    if money:
        without = quote.replace(money.group(0), "", 1).replace("  ", " ").rstrip(".")
        yield f"{without}, by {money.group(0)}."
        yield quote.replace(money.group(0), "a few thousand dollars", 1)
        yield quote.replace(money.group(0), money.group(0).replace("$", ""), 1)
        yield quote.replace(money.group(0), f"{money.group(0)} (not $1K)", 1)


class KnownHoles(unittest.TestCase):
    def check(self, family: str, rewritten: str) -> None:
        scenario, original = first(family)
        self.assertNotEqual(verdict_of(scenario, original, original), "PASS")
        self.assertNotEqual(verdict_of(scenario, original, rewritten), "PASS", rewritten)

    def test_unknown_reason_connector(self):
        self.check("wrong_cause", "Cloud costs rose approximately $38K (122%) compared with "
                                  "September, fueled by the model training run.")
        self.check("wrong_cause", "Cloud costs rose approximately $38K (122%) compared with "
                                  "September; the model training run was the reason.")

    def test_negation_or_contrast_in_the_reason(self):
        self.check("wrong_cause", "Cloud costs rose approximately $38K (122%) compared with "
                                  "September, due to the model training run (not the data migration).")
        self.check("unsupported_cause", "Marketing spend grew approximately $45K (312%) compared "
                                        "with September, driven by the DevSummit sponsorship, "
                                        "not the launch campaign.")
        self.check("unsupported_cause", "Marketing spend grew approximately $45K (312%) compared "
                                        "with September, driven by the DevSummit sponsorship "
                                        "rather than the Q4 launch campaign.")

    def test_unknown_direction_word(self):
        self.check("wrong_direction", "Contractor spend slid approximately $20K (148%) compared "
                                      "with September, because of the mobile app build.")

    def test_figure_after_the_connector(self):
        self.check("wrong_amount", "Occupancy dropped, reflecting the new Austin office lease "
                                   "in September, by $35K.")

    def test_amount_in_words(self):
        self.check("wrong_amount", "The thirty-five thousand dollar decrease in occupancy was "
                                   "reflecting the new Austin office lease in September.")


class Fuzz(unittest.TestCase):
    def test_no_rewording_of_a_defect_is_passed(self):
        tried = 0
        passed: list[str] = []
        for scenario in SCENARIOS:
            for label in scenario.labels:
                if label.requirement == "PASS":
                    continue
                for rewritten in rewordings(label.quote):
                    if rewritten == label.quote:
                        continue
                    tried += 1
                    if verdict_of(scenario, label.quote, rewritten) == "PASS":
                        passed.append(f"{label.family}: {rewritten}")
        self.assertGreater(tried, 500)
        self.assertEqual(passed, [], f"{len(passed)} of {tried} rewordings passed")

    def test_controls_still_pass(self):
        """The guard costs sound explanations nothing."""
        for scenario in SCENARIOS[:20]:
            report = run(scenario.explanation, scenario.ledger)
            for claim in report["claims"]:
                self.assertFalse(any("not read" in a for a in claim["adjustments"]),
                                 claim["claim"]["quote"])


if __name__ == "__main__":
    unittest.main()
