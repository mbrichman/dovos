"""
Test runner framework for migration validation.

Provides structured test execution, reporting, and metrics collection
for the PostgreSQL migration validation test suite.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest


class TestPhase(Enum):
    """Migration test phases."""
    PHASE_1_0 = "1.0_infrastructure"
    PHASE_1_1 = "1.1_contract_compliance"
    PHASE_1_2 = "1.2_search_equivalence"
    PHASE_1_3 = "1.3_data_migration"
    PHASE_1_4 = "1.4_feature_parity"
    PHASE_2 = "2.0_integration"
    PHASE_3 = "3.0_performance"
    PHASE_4 = "4.0_edge_cases"
    PHASE_5 = "5.0_load_testing"


class TestStatus(Enum):
    """Test execution status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Individual test result."""
    test_name: str
    phase: TestPhase
    status: TestStatus
    duration: float
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PhaseReport:
    """Phase execution report."""
    phase: TestPhase
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    results: List[TestResult] = field(default_factory=list)
    coverage_pct: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100
    
    @property
    def is_passing(self) -> bool:
        """Check if phase meets passing criteria (>= 95% success)."""
        return self.success_rate >= 95.0 and self.errors == 0


@dataclass
class MigrationTestReport:
    """Complete migration test report."""
    start_time: str
    end_time: str
    total_duration: float
    phase_reports: List[PhaseReport]
    overall_passed: int
    overall_failed: int
    overall_skipped: int
    overall_errors: int
    
    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate."""
        total = self.overall_passed + self.overall_failed + self.overall_errors
        if total == 0:
            return 0.0
        return (self.overall_passed / total) * 100
    
    @property
    def all_phases_passing(self) -> bool:
        """Check if all phases meet passing criteria."""
        return all(report.is_passing for report in self.phase_reports)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration": self.total_duration,
            "overall_success_rate": self.overall_success_rate,
            "all_phases_passing": self.all_phases_passing,
            "summary": {
                "passed": self.overall_passed,
                "failed": self.overall_failed,
                "skipped": self.overall_skipped,
                "errors": self.overall_errors,
            },
            "phases": [
                {
                    "phase": report.phase.value,
                    "total_tests": report.total_tests,
                    "passed": report.passed,
                    "failed": report.failed,
                    "skipped": report.skipped,
                    "errors": report.errors,
                    "duration": report.duration,
                    "success_rate": report.success_rate,
                    "is_passing": report.is_passing,
                    "coverage_pct": report.coverage_pct,
                }
                for report in self.phase_reports
            ],
        }
    
    def save_json(self, path: Path) -> None:
        """Save report as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def print_summary(self) -> None:
        """Print human-readable summary."""
        print("\n" + "=" * 80)
        print("MIGRATION TEST REPORT")
        print("=" * 80)
        print(f"Start Time: {self.start_time}")
        print(f"End Time: {self.end_time}")
        print(f"Total Duration: {self.total_duration:.2f}s")
        print(f"\nOverall Success Rate: {self.overall_success_rate:.1f}%")
        print(f"All Phases Passing: {'✓ YES' if self.all_phases_passing else '✗ NO'}")
        
        print(f"\nOverall Summary:")
        print(f"  Passed:  {self.overall_passed}")
        print(f"  Failed:  {self.overall_failed}")
        print(f"  Skipped: {self.overall_skipped}")
        print(f"  Errors:  {self.overall_errors}")
        
        print(f"\nPhase Results:")
        for report in self.phase_reports:
            status = "✓" if report.is_passing else "✗"
            print(f"\n  {status} {report.phase.value}")
            print(f"    Tests: {report.passed}/{report.total_tests} passed ({report.success_rate:.1f}%)")
            print(f"    Duration: {report.duration:.2f}s")
            if report.coverage_pct:
                print(f"    Coverage: {report.coverage_pct:.1f}%")
            if report.failed > 0:
                print(f"    ⚠ {report.failed} failed")
            if report.errors > 0:
                print(f"    ⚠ {report.errors} errors")
        
        print("\n" + "=" * 80 + "\n")


class MigrationTestRunner:
    """Test runner for migration validation."""
    
    def __init__(self, output_dir: Path = Path("test_reports")):
        """Initialize test runner."""
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run_phase(
        self,
        phase: TestPhase,
        test_markers: Optional[List[str]] = None,
        pytest_args: Optional[List[str]] = None,
    ) -> PhaseReport:
        """
        Run tests for a specific phase.
        
        Args:
            phase: Test phase to run
            test_markers: Pytest markers to filter tests (e.g., ["migration", "contract"])
            pytest_args: Additional pytest arguments
        
        Returns:
            PhaseReport with execution results
        """
        start_time = time.time()
        
        # Build pytest arguments
        args = pytest_args or []
        
        # Add markers
        if test_markers:
            marker_expr = " and ".join(test_markers)
            args.extend(["-m", marker_expr])
        
        # Add JSON report output
        json_report = self.output_dir / f"{phase.value}_report.json"
        args.extend([
            "--json-report",
            f"--json-report-file={json_report}",
            "--json-report-indent=2",
        ])
        
        # Add verbose output
        args.append("-v")
        
        # Run pytest
        exit_code = pytest.main(args)
        
        duration = time.time() - start_time
        
        # Parse results from JSON report
        if json_report.exists():
            with open(json_report) as f:
                report_data = json.load(f)
            
            summary = report_data.get("summary", {})
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            skipped = summary.get("skipped", 0)
            errors = summary.get("error", 0)
            total = summary.get("total", 0)
            
            # Extract coverage if available
            coverage_pct = None
            if "coverage" in report_data:
                coverage_pct = report_data["coverage"].get("percent_covered")
        else:
            # Fallback if JSON report not available
            passed = 0 if exit_code != 0 else 1
            failed = 1 if exit_code != 0 else 0
            skipped = 0
            errors = 0
            total = 1
            coverage_pct = None
        
        return PhaseReport(
            phase=phase,
            total_tests=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration=duration,
            coverage_pct=coverage_pct,
        )
    
    def run_migration_suite(
        self,
        phases: Optional[List[TestPhase]] = None,
        stop_on_failure: bool = True,
    ) -> MigrationTestReport:
        """
        Run complete migration test suite.
        
        Args:
            phases: Specific phases to run (defaults to all)
            stop_on_failure: Stop execution if a phase fails
        
        Returns:
            MigrationTestReport with complete results
        """
        start_time = datetime.utcnow().isoformat()
        suite_start = time.time()
        
        if phases is None:
            phases = list(TestPhase)
        
        phase_reports = []
        overall_passed = 0
        overall_failed = 0
        overall_skipped = 0
        overall_errors = 0
        
        for phase in phases:
            print(f"\n{'=' * 80}")
            print(f"Running Phase: {phase.value}")
            print(f"{'=' * 80}\n")
            
            # Map phase to appropriate markers
            markers = self._get_markers_for_phase(phase)
            
            phase_report = self.run_phase(phase, test_markers=markers)
            phase_reports.append(phase_report)
            
            overall_passed += phase_report.passed
            overall_failed += phase_report.failed
            overall_skipped += phase_report.skipped
            overall_errors += phase_report.errors
            
            # Check if we should stop
            if stop_on_failure and not phase_report.is_passing:
                print(f"\n⚠ Phase {phase.value} failed. Stopping execution.")
                break
        
        suite_duration = time.time() - suite_start
        end_time = datetime.utcnow().isoformat()
        
        report = MigrationTestReport(
            start_time=start_time,
            end_time=end_time,
            total_duration=suite_duration,
            phase_reports=phase_reports,
            overall_passed=overall_passed,
            overall_failed=overall_failed,
            overall_skipped=overall_skipped,
            overall_errors=overall_errors,
        )
        
        # Save report
        report_path = self.output_dir / f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report.save_json(report_path)
        
        # Print summary
        report.print_summary()
        
        return report
    
    def _get_markers_for_phase(self, phase: TestPhase) -> List[str]:
        """Get pytest markers for a specific phase."""
        marker_map = {
            TestPhase.PHASE_1_0: ["migration", "infrastructure"],
            TestPhase.PHASE_1_1: ["migration", "contract"],
            TestPhase.PHASE_1_2: ["migration", "search"],
            TestPhase.PHASE_1_3: ["migration", "data"],
            TestPhase.PHASE_1_4: ["migration", "feature"],
            TestPhase.PHASE_2: ["integration"],
            TestPhase.PHASE_3: ["perf"],
            TestPhase.PHASE_4: ["migration", "edge"],
            TestPhase.PHASE_5: ["perf", "load"],
        }
        return marker_map.get(phase, ["migration"])


def run_quick_validation() -> bool:
    """
    Run quick validation suite (infrastructure + contract).
    
    Returns:
        True if validation passes, False otherwise
    """
    runner = MigrationTestRunner()
    report = runner.run_migration_suite(
        phases=[TestPhase.PHASE_1_0, TestPhase.PHASE_1_1],
        stop_on_failure=True,
    )
    return report.all_phases_passing


def run_full_validation() -> bool:
    """
    Run full migration validation suite.
    
    Returns:
        True if all phases pass, False otherwise
    """
    runner = MigrationTestRunner()
    report = runner.run_migration_suite(stop_on_failure=False)
    return report.all_phases_passing


if __name__ == "__main__":
    import sys
    
    # Parse command line argument
    mode = sys.argv[1] if len(sys.argv) > 1 else "quick"
    
    if mode == "quick":
        success = run_quick_validation()
    elif mode == "full":
        success = run_full_validation()
    else:
        print(f"Unknown mode: {mode}. Use 'quick' or 'full'.")
        sys.exit(1)
    
    sys.exit(0 if success else 1)
