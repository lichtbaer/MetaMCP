#!/usr/bin/env python3
"""
MetaMCP CLI Tool

A comprehensive command-line interface for managing the MetaMCP project.
This tool bundles all script functionalities in a modular way.
"""

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path


class MetaMCPCLI:
    """Main CLI class for MetaMCP project management."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.scripts_dir = self.project_root / "scripts"

    def run_command(self, command: list[str], cwd: Path | None = None) -> int:
        """Run a shell command and return exit code."""
        try:
            result = subprocess.run(
                command, cwd=cwd or self.project_root, capture_output=True, text=True
            )
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return result.returncode
        except Exception as e:
            print(f"Error running command: {e}", file=sys.stderr)
            return 1

    def _validate_environment_dict(self) -> dict:
        """Return environment validation results as a dictionary (for tests)."""
        import importlib.util
        import sys

        validate_env_path = self.project_root / "scripts" / "validate_env.py"
        spec = importlib.util.spec_from_file_location(
            "validate_env", str(validate_env_path)
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load validate_env.py module spec")
        validate_env = importlib.util.module_from_spec(spec)
        sys.modules["validate_env"] = validate_env
        spec.loader.exec_module(validate_env)
        if hasattr(validate_env, "validate_environment"):
            return validate_env.validate_environment()
        else:
            raise RuntimeError("validate_environment() not found in validate_env.py")

    def validate_environment(self, return_dict: bool = False):
        """Run environment validation. If return_dict is True, return dict for tests."""
        if return_dict:
            return self._validate_environment_dict()
        print("🔍 Validating environment configuration...")
        return self.run_command([sys.executable, "scripts/validate_env.py"])

    def start_development(self) -> int:
        """Start development environment."""
        print("🚀 Starting development environment...")
        script_path = self.scripts_dir / "start-dev.sh"
        if script_path.exists():
            return self.run_command(["bash", str(script_path)])
        else:
            print("❌ start-dev.sh not found", file=sys.stderr)
            return 1

    def start_monitoring(self) -> int:
        """Start monitoring stack."""
        print("📊 Starting monitoring stack...")
        script_path = self.scripts_dir / "start-monitoring.sh"
        if script_path.exists():
            return self.run_command(["bash", str(script_path)])
        else:
            print("❌ start-monitoring.sh not found", file=sys.stderr)
            return 1

    def docker_status(self) -> int:
        """Show Docker container status."""
        print("🐳 Checking Docker container status...")
        return self.run_command(["docker", "compose", "ps"])

    def docker_logs(self, service: str | None = None) -> int:
        """Show Docker logs."""
        if service:
            print(f"📋 Showing logs for {service}...")
            return self.run_command(["docker", "compose", "logs", service])
        else:
            print("📋 Showing all logs...")
            return self.run_command(["docker", "compose", "logs"])

    def docker_restart(self, service: str | None = None) -> int:
        """Restart Docker containers."""
        if service:
            print(f"🔄 Restarting {service}...")
            return self.run_command(["docker", "compose", "restart", service])
        else:
            print("🔄 Restarting all containers...")
            return self.run_command(["docker", "compose", "restart"])

    def docker_stop(self) -> int:
        """Stop all Docker containers."""
        print("🛑 Stopping all containers...")
        return self.run_command(["docker", "compose", "down"])

    def docker_build(self, service: str | None = None, no_cache: bool = False) -> int:
        """Build Docker containers."""
        cmd = ["docker", "compose", "build"]
        if no_cache:
            cmd.append("--no-cache")
        if service:
            cmd.append(service)
            print(f"🔨 Building {service}...")
        else:
            print("🔨 Building all containers...")
        return self.run_command(cmd)

    def setup_environment(self) -> int:
        """Set up the development environment."""
        print("⚙️  Setting up development environment...")

        # Create necessary directories
        dirs = ["logs", "data", "policies/compiled"]
        for dir_name in dirs:
            dir_path = self.project_root / dir_name
            dir_path.mkdir(exist_ok=True)
            print(f"   Created directory: {dir_path}")

        # Check if .env exists
        env_file = self.project_root / ".env"
        env_example = self.project_root / "env.example"

        if not env_file.exists() and env_example.exists():
            print("   Creating .env from template...")
            self.run_command(["cp", "env.example", ".env"])
            print("   ⚠️  Please edit .env file with your configuration")

        print("✅ Environment setup complete")
        return 0

    def install_dependencies(self) -> int:
        """Install Python dependencies."""
        print("📦 Installing Python dependencies...")

        # Check if virtual environment exists
        venv_path = self.project_root / "venv"
        if not venv_path.exists():
            print("   Creating virtual environment...")
            result = self.run_command([sys.executable, "-m", "venv", "venv"])
            if result != 0:
                return result

        # Install requirements
        pip_cmd = (
            [str(venv_path / "bin" / "pip")]
            if os.name != "nt"
            else [str(venv_path / "Scripts" / "pip.exe")]
        )
        return self.run_command(pip_cmd + ["install", "-r", "requirements.txt"])

    def run_tests(self, test_type: str = "all") -> int:
        """Run tests."""
        print(f"🧪 Running {test_type} tests...")

        if test_type == "unit":
            return self.run_command([sys.executable, "-m", "pytest", "tests/unit/"])
        elif test_type == "integration":
            return self.run_command(
                [sys.executable, "-m", "pytest", "tests/integration/"]
            )
        elif test_type == "blackbox":
            return self.run_command([sys.executable, "-m", "pytest", "tests/blackbox/"])
        else:
            return self.run_command([sys.executable, "-m", "pytest", "tests/"])

    def lint_code(self) -> int:
        """Run code linting."""
        print("🔍 Running code linting...")
        return self.run_command([sys.executable, "-m", "flake8", "metamcp/"])

    def format_code(self) -> int:
        """Format code with black."""
        print("🎨 Formatting code...")
        return self.run_command([sys.executable, "-m", "black", "metamcp/"])

    def check_security(self) -> int:
        """Run security checks."""
        print("🔒 Running security checks...")
        return self.run_command([sys.executable, "-m", "bandit", "-r", "metamcp/"])

    def generate_docs(self) -> int:
        """Generate documentation."""
        print("📚 Generating documentation...")
        return self.run_command([sys.executable, "-m", "mkdocs", "build"])

    def serve_docs(self) -> int:
        """Serve documentation locally."""
        print("📖 Serving documentation...")
        return self.run_command([sys.executable, "-m", "mkdocs", "serve"])

    def show_project_info(self) -> int:
        """Show project information."""
        print("ℹ️  MetaMCP Project Information")
        print("=" * 50)

        # Project structure
        print(f"Project Root: {self.project_root}")
        print(f"Scripts Directory: {self.scripts_dir}")

        # Check Docker status
        print("\n🐳 Docker Status:")
        self.docker_status()

        # Check environment
        print("\n🔍 Environment Check:")
        self.validate_environment()

        return 0

    def update_project(self) -> int:
        """Update project dependencies and configuration."""
        print("🔄 Updating project...")

        # Update Python dependencies
        print("📦 Updating Python dependencies...")
        result = self.run_command(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "-r",
                "requirements.txt",
            ]
        )
        if result != 0:
            return result

        # Update Docker images
        print("🐳 Updating Docker images...")
        result = self.run_command(["docker", "compose", "pull"])
        if result != 0:
            return result

        # Update git submodules if any
        if (self.project_root / ".gitmodules").exists():
            print("📚 Updating git submodules...")
            result = self.run_command(["git", "submodule", "update", "--remote"])
            if result != 0:
                return result

        print("✅ Project update complete")
        return 0

    def reset_project(self, hard: bool = False) -> int:
        """Reset project to clean state."""
        if hard:
            print("⚠️  HARD RESET - This will delete all data!")
            confirm = input("Are you sure? Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                print("❌ Reset cancelled")
                return 0

            # Remove all generated files
            dirs_to_remove = ["logs", "data", "venv", "__pycache__", ".pytest_cache"]
            for dir_name in dirs_to_remove:
                dir_path = self.project_root / dir_name
                if dir_path.exists():
                    print(f"🗑️  Removing {dir_name}...")
                    self.run_command(["rm", "-rf", str(dir_path)])

            # Reset Docker
            print("🐳 Resetting Docker...")
            self.run_command(["docker", "compose", "down", "-v"])
            self.run_command(["docker", "system", "prune", "-f"])

            print("✅ Hard reset complete")
        else:
            print("🔄 Soft reset - cleaning temporary files...")

            # Clean temporary files
            temp_patterns = ["*.pyc", "*.pyo", "__pycache__", ".pytest_cache"]
            for pattern in temp_patterns:
                self.run_command(
                    [
                        "find",
                        ".",
                        "-name",
                        pattern,
                        "-type",
                        "d",
                        "-exec",
                        "rm",
                        "-rf",
                        "{}",
                        "+",
                    ]
                )

            # Clean Docker
            print("🐳 Cleaning Docker...")
            self.run_command(["docker", "compose", "down"])

            print("✅ Soft reset complete")

        return 0

    def show_info(self) -> int:
        """Show project information."""
        print("ℹ️  MetaMCP Project Information")
        print("=" * 50)

        # Project structure
        print(f"Project Root: {self.project_root}")
        print(f"Scripts Directory: {self.scripts_dir}")

        # Check Docker status
        print("\n🐳 Docker Status:")
        self.docker_status()

        # Check environment
        print("\n🔍 Environment Check:")
        self.validate_environment()

        return 0


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="MetaMCP CLI Tool - Manage your MetaMCP project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  metamcp validate                    # Validate environment
  metamcp dev start                  # Start development environment
  metamcp docker status              # Show container status
  metamcp docker logs metamcp-server # Show server logs
  metamcp test unit                  # Run unit tests
  metamcp setup                      # Set up environment
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Validate command
    subparsers.add_parser("validate", help="Validate environment configuration")

    # Environment commands
    env_parser = subparsers.add_parser(
        "env", help="Environment variable management commands"
    )
    env_subparsers = env_parser.add_subparsers(dest="env_command")
    env_subparsers.add_parser("show", help="Show current environment variables")
    env_subparsers.add_parser("edit", help="Edit the .env file interactively")
    env_subparsers.add_parser(
        "diff", help="Show differences between .env and env.example"
    )

    # Development commands
    dev_parser = subparsers.add_parser("dev", help="Development commands")
    dev_subparsers = dev_parser.add_subparsers(dest="dev_command")
    dev_subparsers.add_parser("start", help="Start development environment")
    dev_subparsers.add_parser("monitoring", help="Start monitoring stack")
    dev_subparsers.add_parser("setup", help="Set up development environment")
    dev_subparsers.add_parser("install", help="Install dependencies")
    dev_subparsers.add_parser(
        "shell", help="Open interactive shell in development container"
    )
    dev_subparsers.add_parser("logs", help="Show development logs")
    dev_subparsers.add_parser("status", help="Show development services status")

    # Docker commands
    docker_parser = subparsers.add_parser("docker", help="Docker commands")
    docker_subparsers = docker_parser.add_subparsers(dest="docker_command")
    docker_subparsers.add_parser("status", help="Show container status")

    # Docker logs command with optional service argument
    docker_logs_parser = docker_subparsers.add_parser(
        "logs", help="Show container logs"
    )
    docker_logs_parser.add_argument("service", nargs="?", help="Service name")

    # Docker restart command with optional service argument
    docker_restart_parser = docker_subparsers.add_parser(
        "restart", help="Restart containers"
    )
    docker_restart_parser.add_argument("service", nargs="?", help="Service name")

    # Docker stop command
    docker_subparsers.add_parser("stop", help="Stop all containers")

    # Docker build command with optional service argument and no-cache flag
    docker_build_parser = docker_subparsers.add_parser("build", help="Build containers")
    docker_build_parser.add_argument("service", nargs="?", help="Service name")
    docker_build_parser.add_argument(
        "--no-cache", action="store_true", help="Build without cache"
    )

    # Docker prune command
    docker_subparsers.add_parser("prune", help="Clean up Docker resources")

    # Docker exec command
    docker_exec_parser = docker_subparsers.add_parser(
        "exec", help="Execute command in container"
    )
    docker_exec_parser.add_argument("service", help="Service name")
    docker_exec_parser.add_argument(
        "exec_command", nargs="+", help="Command to execute"
    )

    # Monitoring commands
    monitoring_parser = subparsers.add_parser("monitoring", help="Monitoring commands")
    monitoring_subparsers = monitoring_parser.add_subparsers(dest="monitoring_command")
    monitoring_subparsers.add_parser("open", help="Open monitoring URLs in browser")
    monitoring_subparsers.add_parser("test", help="Test monitoring endpoints")

    # Testing commands
    test_parser = subparsers.add_parser("test", help="Testing commands")
    test_subparsers = test_parser.add_subparsers(dest="test_command")
    test_subparsers.add_parser("unit", help="Run unit tests")
    test_subparsers.add_parser("integration", help="Run integration tests")
    test_subparsers.add_parser("blackbox", help="Run blackbox tests")
    test_subparsers.add_parser("all", help="Run all tests")
    test_subparsers.add_parser("coverage", help="Run tests with coverage report")
    test_subparsers.add_parser("report", help="Generate test report")
    test_subparsers.add_parser("performance", help="Run performance tests")
    test_subparsers.add_parser("security", help="Run security tests")
    test_subparsers.add_parser("typecheck", help="Run type checking")

    # Database commands
    db_parser = subparsers.add_parser("db", help="Database commands")
    db_subparsers = db_parser.add_subparsers(dest="db_command")
    db_subparsers.add_parser("migrate", help="Run database migrations")
    db_subparsers.add_parser("reset", help="Reset database")
    db_subparsers.add_parser("shell", help="Open database shell")
    db_subparsers.add_parser("backup", help="Create database backup")
    db_subparsers.add_parser("restore", help="Restore database from backup")

    # Code quality commands
    quality_parser = subparsers.add_parser("quality", help="Code quality commands")
    quality_subparsers = quality_parser.add_subparsers(dest="quality_command")
    quality_subparsers.add_parser("lint", help="Run code linting")
    quality_subparsers.add_parser("format", help="Format code")
    quality_subparsers.add_parser("security", help="Run security checks")

    # Documentation commands
    docs_parser = subparsers.add_parser("docs", help="Documentation commands")
    docs_subparsers = docs_parser.add_subparsers(dest="docs_command")
    docs_subparsers.add_parser("build", help="Build documentation")
    docs_subparsers.add_parser("serve", help="Serve documentation locally")
    docs_subparsers.add_parser("deploy", help="Deploy documentation")
    docs_subparsers.add_parser("open", help="Open documentation in browser")
    docs_subparsers.add_parser("api", help="Generate API documentation")
    docs_subparsers.add_parser("validate", help="Validate documentation")

    # Policy commands
    policy_parser = subparsers.add_parser("policy", help="Policy management commands")
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command")
    policy_subparsers.add_parser("compile", help="Compile OPA policies")
    policy_subparsers.add_parser("test", help="Test policies")
    policy_subparsers.add_parser("validate", help="Validate policy syntax")

    # User management commands
    user_parser = subparsers.add_parser("user", help="User management commands")
    user_subparsers = user_parser.add_subparsers(dest="user_command")
    user_subparsers.add_parser("list", help="List users")
    user_subparsers.add_parser("add", help="Add user")
    user_subparsers.add_parser("remove", help="Remove user")
    user_subparsers.add_parser("roles", help="Manage user roles")

    # Misc utility commands
    subparsers.add_parser("cleanup", help="Clean up temporary files and caches")
    subparsers.add_parser("open", help="Open service URLs in browser")
    subparsers.add_parser("support", help="Show support information")

    # Update and reset commands
    subparsers.add_parser(
        "update", help="Update dependencies, Docker images, and database migrations"
    )
    reset_parser = subparsers.add_parser(
        "reset", help="Reset project state (database, cache, logs, etc.)"
    )
    reset_parser.add_argument(
        "--hard", action="store_true", help="Full reset including .env and volumes"
    )

    # Info command
    subparsers.add_parser("info", help="Show project information")

    return parser


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    cli = MetaMCPCLI()

    try:
        if args.command == "validate":
            return cli.validate_environment()

        elif args.command == "env":
            if args.env_command == "show":
                print("🔍 Showing current environment variables...")
                env_file = cli.project_root / ".env"
                if env_file.exists():
                    with open(env_file) as f:
                        print(f.read())
                else:
                    print("❌ .env file not found.")
                return 0
            elif args.env_command == "edit":
                print("🖊️  Editing .env file interactively...")
                env_file = cli.project_root / ".env"
                if env_file.exists():
                    with open(env_file) as f:
                        lines = f.readlines()
                    with open(env_file, "w") as f:
                        for line in lines:
                            f.write(line)
                            print(line, end="")
                            if line.strip() != "":
                                print("  ", end="")  # Indent for editing
                        print("\nEdit .env file (type 'save' to save, 'quit' to exit):")
                        while True:
                            try:
                                line = input()
                                if line.strip() == "save":
                                    break
                                elif line.strip() == "quit":
                                    print("Operation cancelled by user.")
                                    return 1
                                else:
                                    f.write(line + "\n")
                            except EOFError:
                                print("\nOperation cancelled by user.")
                                return 1
                        print("✅ .env file updated.")
                else:
                    print("❌ .env file not found. Please run 'metamcp setup' first.")
                    return 1
            elif args.env_command == "diff":
                env_file = cli.project_root / ".env"
                env_example = cli.project_root / "env.example"
                if env_file.exists() and env_example.exists():
                    print("🔄 Comparing .env and env.example...")
                    env_diff = subprocess.run(
                        ["diff", str(env_file), str(env_example)],
                        capture_output=True,
                        text=True,
                    )
                    if env_diff.stdout:
                        print("🔍 Differences found:")
                        print(env_diff.stdout)
                    if env_diff.stderr:
                        print(env_diff.stderr, file=sys.stderr)
                    if not env_diff.stdout and not env_diff.stderr:
                        print("✅ No differences found.")
                else:
                    print(
                        "❌ .env or env.example not found. Please run 'metamcp setup' first."
                    )
                    return 1
            else:
                parser.print_help()
                return 1

        elif args.command == "update":
            print("⬆️  Updating dependencies and project state...")
            # Update Python dependencies
            venv_path = cli.project_root / "venv"
            pip_cmd = (
                [str(venv_path / "bin" / "pip")]
                if os.name != "nt"
                else [str(venv_path / "Scripts" / "pip.exe")]
            )
            print("   Upgrading Python packages...")
            cli.run_command(
                pip_cmd + ["install", "--upgrade", "-r", "requirements.txt"]
            )
            # Update Docker images
            print("   Pulling latest Docker images...")
            cli.run_command(["docker", "compose", "pull"])
            # Optional: Datenbankmigrationen (Platzhalter)
            # print("   Running database migrations...")
            # cli.run_command([sys.executable, "-m", "alembic", "upgrade", "head"])
            print("✅ Update complete.")
            return 0

        elif args.command == "reset":
            print("⚠️  Resetting project state...")
            confirm = input(
                "Are you sure you want to reset the project? This will delete database, cache, logs, and more. Type 'yes' to continue: "
            )
            if confirm.strip().lower() != "yes":
                print("Aborted.")
                return 1
            # Stop containers
            cli.run_command(["docker", "compose", "down", "-v"])
            # Remove logs, data, cache
            for folder in ["logs", "data", "__pycache__"]:
                folder_path = cli.project_root / folder
                if folder_path.exists():
                    print(f"   Removing {folder_path}")
                    cli.run_command(["rm", "-rf", str(folder_path)])
            # Optionally remove .env and volumes
            if getattr(args, "hard", False):
                env_file = cli.project_root / ".env"
                if env_file.exists():
                    print("   Removing .env file")
                    env_file.unlink()
                print("   Removing Docker volumes...")
                cli.run_command(["docker", "volume", "prune", "-f"])
            print("✅ Project reset complete.")
            return 0

        elif args.command == "dev":
            if args.dev_command == "start":
                return cli.start_development()
            elif args.dev_command == "monitoring":
                return cli.start_monitoring()
            elif args.dev_command == "setup":
                return cli.setup_environment()
            elif args.dev_command == "install":
                return cli.install_dependencies()
            elif args.dev_command == "shell":
                print("🐳 Opening interactive shell in development container...")
                return cli.run_command(
                    ["docker", "compose", "exec", "metamcp-dev", "bash"]
                )
            elif args.dev_command == "logs":
                print("📋 Showing development logs...")
                return cli.docker_logs("metamcp-dev")
            elif args.dev_command == "status":
                print("🐳 Checking development services status...")
                return cli.docker_status()
            else:
                parser.print_help()
                return 1

        elif args.command == "docker":
            if args.docker_command == "status":
                return cli.docker_status()
            elif args.docker_command == "logs":
                return cli.docker_logs(args.service)
            elif args.docker_command == "restart":
                return cli.docker_restart(args.service)
            elif args.docker_command == "stop":
                return cli.docker_stop()
            elif args.docker_command == "build":
                return cli.docker_build(args.service, args.no_cache)
            elif args.docker_command == "prune":
                print("🧹 Cleaning up Docker resources...")
                return cli.run_command(["docker", "system", "prune", "-f", "--volumes"])
            elif args.docker_command == "exec":
                print(f"🐳 Executing command in {args.service} container...")
                cmd = ["docker", "compose", "exec", args.service] + args.exec_command
                return cli.run_command(cmd)
            else:
                parser.print_help()
                return 1

        elif args.command == "monitoring":
            if args.monitoring_command == "open":
                print("🌐 Opening monitoring URLs in browser...")
                return cli.run_command(
                    ["xdg-open", "http://localhost:9000"]
                )  # Assuming a default port for monitoring
            elif args.monitoring_command == "test":
                print("🧪 Testing monitoring endpoints...")
                return cli.run_command([sys.executable, "scripts/test_monitoring.py"])
            else:
                parser.print_help()
                return 1

        elif args.command == "test":
            test_type = args.test_command or "all"
            if test_type == "coverage":
                return cli.run_tests("all")  # Run with coverage
            elif test_type == "report":
                print("📊 Generating test report...")
                return cli.run_command(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "--html=test_report.html",
                        "--self-contained-html",
                    ]
                )
            elif test_type == "performance":
                return cli.run_tests("performance")
            elif test_type == "security":
                return cli.run_tests("security")
            elif test_type == "typecheck":
                print("🔍 Running type checking...")
                return cli.run_command([sys.executable, "-m", "mypy", "metamcp/"])
            else:
                return cli.run_tests(test_type)

        elif args.command == "quality":
            if args.quality_command == "lint":
                return cli.lint_code()
            elif args.quality_command == "format":
                return cli.format_code()
            elif args.quality_command == "security":
                return cli.check_security()
            else:
                parser.print_help()
                return 1

        elif args.command == "docs":
            if args.docs_command == "build":
                return cli.generate_docs()
            elif args.docs_command == "serve":
                return cli.serve_docs()
            elif args.docs_command == "deploy":
                print("🚀 Deploying documentation...")
                return cli.run_command([sys.executable, "-m", "mkdocs", "gh-deploy"])
            elif args.docs_command == "open":
                print("📖 Opening documentation in browser...")
                return cli.run_command(
                    ["xdg-open", "http://localhost:9000"]
                )  # Assuming a default port for docs
            elif args.docs_command == "api":
                print("📚 Generating API documentation...")
                return cli.run_command(
                    [sys.executable, "-m", "mkdocs", "json", "-o", "site/api.json"]
                )
            elif args.docs_command == "validate":
                print("🔍 Validating documentation...")
                return cli.run_command(
                    [sys.executable, "-m", "mkdocs", "build", "--strict"]
                )
            else:
                parser.print_help()
                return 1

        elif args.command == "policy":
            if args.policy_command == "compile":
                print("🔨 Compiling OPA policies...")
                return cli.run_command(["opa", "test", "policies/"])
            elif args.policy_command == "test":
                print("🧪 Testing policies...")
                return cli.run_command(["opa", "test", "policies/"])
            elif args.policy_command == "validate":
                print("🔍 Validating policy syntax...")
                return cli.run_command(["opa", "test", "policies/"])
            else:
                parser.print_help()
                return 1

        elif args.command == "user":
            if args.user_command == "list":
                print("👥 Listing users...")
                return cli.run_command([sys.executable, "scripts/list_users.py"])
            elif args.user_command == "add":
                print("👥 Adding user...")
                username = input("Enter username: ")
                password = input("Enter password: ")
                return cli.run_command(
                    [sys.executable, "scripts/add_user.py", username, password]
                )
            elif args.user_command == "remove":
                print("👥 Removing user...")
                username = input("Enter username to remove: ")
                return cli.run_command(
                    [sys.executable, "scripts/remove_user.py", username]
                )
            elif args.user_command == "roles":
                print("👥 Managing user roles...")
                username = input("Enter username to manage roles: ")
                role = input("Enter new role (e.g., admin, user): ")
                return cli.run_command(
                    [sys.executable, "scripts/manage_user_roles.py", username, role]
                )
            else:
                parser.print_help()
                return 1

        elif args.command == "db":
            if args.db_command == "migrate":
                print("🔄 Running database migrations...")
                return cli.run_command(
                    [sys.executable, "-m", "alembic", "upgrade", "head"]
                )
            elif args.db_command == "reset":
                print("⚠️  Resetting database...")
                confirm = input(
                    "Are you sure you want to reset the database? This will delete all data. Type 'yes' to continue: "
                )
                if confirm.strip().lower() != "yes":
                    print("Aborted.")
                    return 1
                return cli.run_command(
                    [sys.executable, "-m", "alembic", "downgrade", "base"]
                )
            elif args.db_command == "shell":
                print("🐳 Opening database shell...")
                return cli.run_command(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "metamcp-db",
                        "psql",
                        "-U",
                        "postgres",
                        "-d",
                        "metamcp",
                    ]
                )
            elif args.db_command == "backup":
                print("💾 Creating database backup...")
                backup_file = (
                    f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
                )
                return cli.run_command(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "metamcp-db",
                        "pg_dump",
                        "-U",
                        "postgres",
                        "-d",
                        "metamcp",
                        "-f",
                        str(cli.project_root / backup_file),
                    ]
                )
            elif args.db_command == "restore":
                print("💾 Restoring database from backup...")
                backup_file = input(
                    "Enter backup file name (e.g., backup_20231027_123456.sql): "
                )
                if not (cli.project_root / backup_file).exists():
                    print(f"❌ Backup file '{backup_file}' not found.")
                    return 1
                return cli.run_command(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "metamcp-db",
                        "psql",
                        "-U",
                        "postgres",
                        "-d",
                        "metamcp",
                        "-f",
                        str(cli.project_root / backup_file),
                    ]
                )
            else:
                parser.print_help()
                return 1

        elif args.command == "info":
            return cli.show_project_info()

        elif args.command == "update":
            return cli.update_project()

        elif args.command == "reset":
            return cli.reset_project(args.hard)

        elif args.command == "cleanup":
            print("🧹 Cleaning up temporary files and caches...")
            # Remove __pycache__
            for folder in ["__pycache__"]:
                folder_path = cli.project_root / folder
                if folder_path.exists():
                    print(f"   Removing {folder_path}")
                    cli.run_command(["rm", "-rf", str(folder_path)])
            # Clear Docker cache
            print("   Clearing Docker cache...")
            cli.run_command(["docker", "system", "prune", "-f", "--volumes"])
            print("✅ Cleanup complete.")
            return 0

        elif args.command == "support":
            print("ℹ️  Support Information")
            print("=" * 50)
            print(f"Project Root: {cli.project_root}")
            print(f"Scripts Directory: {cli.scripts_dir}")
            print(f"Python executable: {sys.executable}")
            print(f"Operating System: {sys.platform}")
            print(
                f"Docker Compose Version: {cli.run_command(['docker', 'compose', '--version'])}"
            )
            print(
                f"Docker Version: {cli.run_command(['docker', 'version', '--format', '{{.Server.Version}}'])}"
            )
            print(
                f"Python Packages: {cli.run_command([str(cli.project_root / 'venv' / 'bin' / 'pip'), 'list'])}"
            )
            return 0

        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
