import json
import sys
from pathlib import Path

report_path = Path("security-demo/simulated-trivy-report.json")

with report_path.open(encoding="utf-8") as file:
    report = json.load(file)

# Защита от случайного использования реального отчёта
if report.get("demo_type") != "SIMULATED":
    print("ERROR: Expected a SIMULATED report")
    sys.exit(2)

findings = [
    vulnerability
    for result in report.get("Results", [])
    for vulnerability in result.get("Vulnerabilities", [])
]

critical = [
    finding
    for finding in findings
    if finding.get("Severity", "").upper() == "CRITICAL"
]

print("SIMULATED SECURITY GATE POLICY TEST")
print(f"Total findings: {len(findings)}")
print(f"Critical findings: {len(critical)}")

if critical:
    for finding in critical:
        print(
            f"POLICY VIOLATION: {finding.get('VulnerabilityID')} "
            f"({finding.get('Severity')})"
        )

    print("SECURITY GATE: FAILED (expected demonstration result)")
    sys.exit(1)

print("SECURITY GATE: PASSED")
