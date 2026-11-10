"""Shared fail-closed input checks; source links are not semantic proof."""
from datetime import date


FRAMEWORKS = {
    "ICAN+": ("I", "C", "A", "N"),
    "CAR": ("Challenge", "Action", "Result"),
    "Approach": ("Understand", "Choose", "Test and measure"),
    "STAR": ("Situation", "Task", "Action", "Result"),
    "Present–Past–Future": ("Present", "Past", "Future"),
    "PREP": ("Point", "Reason", "Example", "Point again"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def refs(value, sources, required=False, kind=None):
    require(isinstance(value, list), "Sources must be an array.")
    require(all(isinstance(k, str) and k in sources for k in value), "Unknown source reference.")
    require(not required or bool(value), "Evidence references are required.")
    require(not kind or any(sources[k].get("kind") == kind for k in value),
            f"A {kind} source is required.")


def pay(value):
    if value is None:
        return
    require(isinstance(value, dict), "Pay must be a range or null.")
    require(type(value.get("low")) is int and type(value.get("high")) is int,
            "Pay figures must be integers.")
    require(0 < value["low"] <= value["high"], "Pay range must be positive and ordered.")
    require(isinstance(value.get("currency"), str) and len(value["currency"]) == 3
            and value["currency"].isalpha() and value["currency"].isupper(), "Use an ISO currency code.")
    require(text(value.get("basis")), "State the pay basis, period and inclusions.")


def base(observed, report):
    require(isinstance(observed, dict) and isinstance(report, dict), "Inputs must be objects.")
    date.fromisoformat(observed["checked_on"])
    vacancy = observed["vacancy"]
    for key in ("id", "employer", "title", "mode", "employment", "source"):
        require(text(vacancy.get(key)), f"Vacancy needs {key}.")
    require(vacancy.get("status") in {"open", "closed", "unknown"}, "Invalid vacancy state.")
    require(isinstance(vacancy.get("locations"), list) and vacancy["locations"]
            and all(text(v) for v in vacancy["locations"]), "Record locations or an explicit unknown location.")
    if vacancy.get("deadline") is not None:
        date.fromisoformat(vacancy["deadline"])
    submission = observed["submission"]
    require(submission.get("status") in {"submitted", "not_submitted", "unconfirmed"},
            "Invalid submission state.")
    require(text(submission.get("description")), "Describe submission evidence or its absence.")
    sources = observed["sources"]
    require(isinstance(sources, dict) and bool(sources), "A source ledger is required.")
    for key, source in sources.items():
        require(text(key) and isinstance(source, dict), "Invalid source entry.")
        require(all(text(source.get(k)) for k in ("kind", "label", "locator")), "Source needs kind, label and locator.")
    refs([vacancy["source"]], sources, kind="employer")
    refs([submission["source"]], sources, kind="application_record")
    pay(observed.get("employer_pay"))
    pay(report.get("estimated_pay"))
    for row in report["fit"]:
        require(row.get("level") in {"Direct", "Direct with a gap", "Transferable", "Gap"}, "Invalid fit level.")
        require(text(row.get("requirement")) and text(row.get("detail")), "Fit needs a requirement and explanation.")
    for story in report["stories"]:
        refs(story["sources"], sources, required=True, kind="candidate")
    return sources


def interview(observed, report, guide, require_strategy=True):
    base(observed, report)
    additions = guide["framework_sources"]
    require(isinstance(additions, dict), "Framework sources must be an object.")
    require(not set(additions).intersection(observed["sources"]), "Framework sources cannot overwrite evidence IDs.")
    sources = observed["sources"] | additions
    for source in additions.values():
        require(text(source.get("label")), "Framework sources need labels.")
    for key in ("opening", "why", "recruiter", "manager", "recovery"):
        require(text(guide.get(key)), f"Interview guide needs {key}.")
    refs(guide["opening_sources"], sources, required=True, kind="candidate")
    refs(guide["why_sources"], sources, required=True)
    require(len(guide["cards"]) >= 2, "Include at least two experience cards.")
    for card in guide["cards"]:
        require(card.get("kind") == "past_experience", "Label each experience card as past_experience.")
        for key in ("question", "answer", "follow_up"):
            require(text(card.get(key)), f"Each card needs {key}.")
        require(isinstance(card.get("bullets"), list) and len(card["bullets"]) >= 2
                and all(text(v) for v in card["bullets"]), "Each card needs speaking bullets.")
        require(isinstance(card.get("cues"), list) and 2 <= len(card["cues"]) <= 6
                and all(text(v) for v in card["cues"]), "Each card needs two to six cues.")
        refs(card["sources"], sources, required=True, kind="candidate")
    require(guide["pilot"].get("kind") == "proposal", "Label the scenario as a proposal.")
    refs(guide["pilot"]["sources"], sources, required=True, kind="employer")
    strategy = guide.get("strategy")
    require(not require_strategy or isinstance(strategy, dict), "Interview Prep needs an answer strategy.")
    if strategy is not None:
        methods = strategy["methods"]
        require(isinstance(methods, list) and bool(methods), "Choose at least one answer framework.")
        names = [m["name"] for m in methods]
        require(len(names) == len(set(names)), "Framework names must be unique.")
        defaults = strategy.get("defaults", names[:3])
        require(isinstance(defaults, list) and 1 <= len(defaults) <= 3
                and set(defaults) <= set(names), "Choose one to three included default frameworks.")
        for method in methods:
            require(method.get("kind") in {"past_experience", "proposal", "positioning"}, "Label framework example type.")
            require(text(method.get("question")) and text(method.get("cues")), "Framework needs question and cues.")
            steps = method["steps"]
            require(isinstance(steps, list) and len(steps) >= 2, "Framework needs worked steps.")
            require(all(isinstance(s, list) and len(s) == 2 and all(text(v) for v in s) for s in steps),
                    "Each framework step needs a label and worked example.")
            if method["name"] in FRAMEWORKS:
                expected = FRAMEWORKS[method["name"]]
                labels = [s[0].split(" · ")[0] for s in steps]
                require(tuple(labels[:len(expected)]) == expected, "Framework steps are incomplete or out of order.")
                require(len(labels) == len(expected) or (method["name"] == "ICAN+" and len(labels) == 5 and labels[-1] == "+"),
                        "Unexpected framework steps.")
            else:
                require(text(method.get("definition")), "Custom frameworks need a definition.")
            refs(method["sources"], sources, required=True,
                 kind="candidate" if method["kind"] in {"past_experience", "positioning"} else None)
            if method["name"] in {"CAR", "STAR"}:
                require(method["kind"] == "past_experience", "CAR/STAR examples must describe real experience.")
        require(text(strategy.get("selection")) and text(strategy.get("rehearsal")), "Give selection and rehearsal guidance.")
    return sources
