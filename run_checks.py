"""Focused test and deliberate regression evidence; no external services."""
import io
from pathlib import Path
import unittest
from experiment import CASES, database, lookup, write_json

ROOT=Path(__file__).resolve().parent
if __name__ == "__main__":
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"))
    result=unittest.TextTestRunner(stream=io.StringIO(),verbosity=2).run(suite)
    report={"tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),"passed":result.wasSuccessful()}
    write_json(ROOT/"artifacts/tests.json",report)
    db=database()
    mutations=[]
    try:
        for mutant in ("email_fallback_mutant","provider_omitted_mutant"):
            mismatches=[]
            for case in CASES:
                actual=lookup(db,case.assertion,mutant)
                if actual!=case.expected_bound:
                    mismatches.append({"case":case.name,"expected":case.expected_bound,"actual":actual})
            mutations.append({"mutation":mutant,"detected":bool(mismatches),"mismatches":mismatches})
    finally: db.close()
    write_json(ROOT/"artifacts/mutations.json",{"checks":mutations,"all_detected":all(m["detected"] for m in mutations)})
    print(report)
    print({m["mutation"]:len(m["mismatches"]) for m in mutations})
    if not result.wasSuccessful() or not all(m["detected"] for m in mutations): raise SystemExit(1)
