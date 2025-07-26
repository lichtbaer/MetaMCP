#!/usr/bin/env python3
"""
Comprehensive Test Runner for MetaMCP

This script runs all test suites and generates detailed reports including:
- Unit tests
- Integration tests
- Performance tests
- Security tests
- Blackbox tests
- Coverage reports
- Performance benchmarks
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


class TestRunner:
    """Comprehensive test runner for MetaMCP."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_results = {}
        self.start_time = None
        self.end_time = None

    def run_command(self, cmd: list[str], timeout: int = 300) -> dict:
        """Run a command and return results."""
        try:
            start_time = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root,
            )
            end_time = time.time()

            return {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": end_time - start_time,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": "Command timed out",
                "execution_time": timeout,
                "success": False,
            }
        except Exception as e:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "execution_time": 0,
                "success": False,
            }

    def run_unit_tests(self) -> dict:
        """Run unit tests."""
        print("🧪 Running unit tests...")

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/",
            "-v",
            "--tb=short",
            "--junitxml=test-results/unit-tests.xml",
            "--cov=metamcp",
            "--cov-report=html:test-results/coverage/html",
            "--cov-report=term-missing",
            "--cov-report=xml:test-results/coverage.xml",
        ]

        return self.run_command(cmd)

    def run_integration_tests(self) -> dict:
        """Run integration tests."""
        print("🔗 Running integration tests...")

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/",
            "-v",
            "--tb=short",
            "--junitxml=test-results/integration-tests.xml",
            "-m",
            "integration",
        ]

        return self.run_command(cmd)

    def run_performance_tests(self) -> dict:
        """Run performance tests."""
        print("⚡ Running performance tests...")

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/performance/",
            "-v",
            "--tb=short",
            "--junitxml=test-results/performance-tests.xml",
            "-m",
            "performance or load or stress or benchmark",
        ]

        return self.run_command(cmd)

    def run_security_tests(self) -> dict:
        """Run security tests."""
        print("🔒 Running security tests...")

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/security/",
            "-v",
            "--tb=short",
            "--junitxml=test-results/security-tests.xml",
            "-m",
            "security",
        ]

        return self.run_command(cmd)

    def run_blackbox_tests(self) -> dict:
        """Run blackbox tests."""
        print("📦 Running blackbox tests...")

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/blackbox/",
            "-v",
            "--tb=short",
            "--junitxml=test-results/blackbox-tests.xml",
        ]

        return self.run_command(cmd)

    def run_coverage_analysis(self) -> dict:
        """Run coverage analysis."""
        print("📊 Running coverage analysis...")

        cmd = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "-m",
            "pytest",
            "tests/",
            "--cov=metamcp",
            "--cov-report=html:test-results/coverage/html",
            "--cov-report=term-missing",
            "--cov-report=xml:test-results/coverage.xml",
        ]

        return self.run_command(cmd)

    def run_linting(self) -> dict:
        """Run code linting."""
        print("🔍 Running code linting...")

        cmd = [
            sys.executable,
            "-m",
            "flake8",
            "metamcp/",
            "--max-line-length=88",
            "--extend-ignore=E203,W503",
        ]

        return self.run_command(cmd)

    def run_type_checking(self) -> dict:
        """Run type checking."""
        print("🔍 Running type checking...")

        cmd = [
            sys.executable,
            "-m",
            "mypy",
            "metamcp/",
            "--ignore-missing-imports",
            "--show-error-codes",
        ]

        return self.run_command(cmd)

    def run_security_scanning(self) -> dict:
        """Run security scanning."""
        print("🔒 Running security scanning...")

        cmd = [
            sys.executable,
            "-m",
            "bandit",
            "-r",
            "metamcp/",
            "-f",
            "json",
            "-o",
            "test-results/security-scan.json",
        ]

        return self.run_command(cmd)

    def create_test_directories(self):
        """Create test result directories."""
        test_dirs = [
            "test-results",
            "test-results/coverage",
            "test-results/coverage/html",
            "test-results/performance",
            "test-results/security",
        ]

        for dir_path in test_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    def run_all_tests(self) -> dict:
        """Run all test suites."""
        print("🚀 Starting comprehensive test suite...")
        self.start_time = time.time()

        # Create test directories
        self.create_test_directories()

        # Run all test suites
        test_suites = {
            "unit_tests": self.run_unit_tests,
            "integration_tests": self.run_integration_tests,
            "performance_tests": self.run_performance_tests,
            "security_tests": self.run_security_tests,
            "blackbox_tests": self.run_blackbox_tests,
            "coverage_analysis": self.run_coverage_analysis,
            "linting": self.run_linting,
            "type_checking": self.run_type_checking,
            "security_scanning": self.run_security_scanning,
        }

        results = {}
        for suite_name, suite_func in test_suites.items():
            print(f"\n{'='*60}")
            print(f"Running {suite_name}...")
            print(f"{'='*60}")

            result = suite_func()
            results[suite_name] = result

            if result["success"]:
                print(f"✅ {suite_name} completed successfully")
            else:
                print(f"❌ {suite_name} failed")
                print(f"Error: {result['stderr']}")

        self.end_time = time.time()
        self.test_results = results

        return results

    def generate_summary_report(self) -> dict:
        """Generate a summary report."""
        if not self.test_results:
            return {"error": "No test results available"}

        total_tests = len(self.test_results)
        successful_tests = sum(
            1 for result in self.test_results.values() if result["success"]
        )
        failed_tests = total_tests - successful_tests

        sum(result["execution_time"] for result in self.test_results.values())

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_execution_time": (
                self.end_time - self.start_time if self.end_time else 0
            ),
            "test_suites": {
                "total": total_tests,
                "successful": successful_tests,
                "failed": failed_tests,
                "success_rate": (
                    (successful_tests / total_tests * 100) if total_tests > 0 else 0
                ),
            },
            "detailed_results": self.test_results,
            "recommendations": self.generate_recommendations(),
        }

        return summary

    def generate_recommendations(self) -> list[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        if not self.test_results:
            return ["No test results available"]

        # Check for failed tests
        failed_suites = [
            name for name, result in self.test_results.items() if not result["success"]
        ]

        if failed_suites:
            recommendations.append(
                f"Fix failing test suites: {', '.join(failed_suites)}"
            )

        # Check execution times
        slow_tests = []
        for name, result in self.test_results.items():
            if result["execution_time"] > 60:  # More than 60 seconds
                slow_tests.append(f"{name} ({result['execution_time']:.1f}s)")

        if slow_tests:
            recommendations.append(
                f"Optimize slow test suites: {', '.join(slow_tests)}"
            )

        # Check coverage
        if (
            "coverage_analysis" in self.test_results
            and self.test_results["coverage_analysis"]["success"]
        ):
            # Parse coverage output to check coverage percentage
            coverage_output = self.test_results["coverage_analysis"]["stdout"]
            if "TOTAL" in coverage_output:
                # Extract coverage percentage
                for line in coverage_output.split("\n"):
                    if "TOTAL" in line:
                        try:
                            coverage_parts = line.split()
                            coverage_percentage = float(coverage_parts[-1].rstrip("%"))
                            if coverage_percentage < 80:
                                recommendations.append(
                                    f"Increase test coverage (currently {coverage_percentage:.1f}%)"
                                )
                        except (ValueError, IndexError):
                            pass
                        break

        # Check security issues
        if (
            "security_scanning" in self.test_results
            and self.test_results["security_scanning"]["success"]
        ):
            try:
                security_file = Path("test-results/security-scan.json")
                if security_file.exists():
                    with open(security_file) as f:
                        security_data = json.load(f)
                        if security_data.get("results"):
                            high_severity = [
                                r
                                for r in security_data["results"]
                                if r.get("issue_severity") == "HIGH"
                            ]
                            if high_severity:
                                recommendations.append(
                                    f"Fix {len(high_severity)} high severity security issues"
                                )
            except Exception:
                pass

        if not recommendations:
            recommendations.append("All tests passed successfully!")

        return recommendations

    def save_report(self, report: dict, filename: str = None):
        """Save test report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test-results/test-report-{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        print(f"📄 Test report saved to: {filename}")

    def print_summary(self, report: dict):
        """Print a human-readable summary."""
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)

        suites = report["test_suites"]
        print(f"Total Test Suites: {suites['total']}")
        print(f"Successful: {suites['successful']}")
        print(f"Failed: {suites['failed']}")
        print(f"Success Rate: {suites['success_rate']:.1f}%")
        print(f"Total Execution Time: {report['total_execution_time']:.1f} seconds")

        print("\n📋 RECOMMENDATIONS:")
        for i, recommendation in enumerate(report["recommendations"], 1):
            print(f"{i}. {recommendation}")

        print("\n📁 Test Results Location:")
        print("- Coverage Report: test-results/coverage/html/index.html")
        print("- JUnit XML: test-results/*.xml")
        print("- Security Scan: test-results/security-scan.json")
        print("- Detailed Report: test-results/test-report-*.json")

        print("=" * 80)


def main():
    """Main function to run all tests."""
    runner = TestRunner()

    try:
        # Run all tests
        runner.run_all_tests()

        # Generate and save report
        report = runner.generate_summary_report()
        runner.save_report(report)

        # Print summary
        runner.print_summary(report)

        # Exit with appropriate code
        if report["test_suites"]["failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n❌ Test execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
