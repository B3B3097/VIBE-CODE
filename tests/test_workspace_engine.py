#!/usr/bin/env python3
"""
tests/test_workspace_engine.py — Unit tests for WorkspaceEngine
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.workspace_engine import WorkspaceEngine, WorkspaceScanner, TaskPlanner, TaskStatus


class TestWorkspaceEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_workspace_")
        self.engine = WorkspaceEngine(workspace_path=self.test_dir, prompt="Build high performance system")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scanner_empty(self):
        scanner = WorkspaceScanner(self.test_dir)
        report = scanner.scan()
        self.assertEqual(report["stats"]["total_files"], 0)

    def test_planner_generates_tasks(self):
        planner = TaskPlanner("Build payment gateway")
        tasks = planner.plan_architecture()
        self.assertGreaterEqual(len(tasks), 5)
        self.assertEqual(tasks[0].status, TaskStatus.PENDING)

    def test_workflow_execution(self):
        res = self.engine.execute_workflow()
        self.assertEqual(res["status"], "success")
        self.assertIn("models.py", res["files"])
        self.assertIn("engine.py", res["files"])
        self.assertIn("main.py", res["files"])
        self.assertIn("test_app.py", res["files"])
        self.assertIn("TODO.md", res["files"])

        # Verify TODO.md contents
        todo_content = (Path(self.test_dir) / "TODO.md").read_text(encoding="utf-8")
        self.assertIn("[x]", todo_content)
        self.assertIn("TASK-01", todo_content)

    def test_ast_inspector(self):
        scanner = WorkspaceScanner(self.test_dir)
        code = "class MyClass:\n    def my_method(self):\n        pass\n"
        ast_info = scanner.inspect_python_ast(code)
        self.assertTrue(ast_info["valid"])
        self.assertIn("MyClass", ast_info["classes"])
        self.assertIn("my_method", ast_info["functions"])


if __name__ == "__main__":
    unittest.main()
