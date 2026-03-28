from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from deletebench.utils.diff_utils import diff_snapshots


EVAL_SCRIPT = dedent(
    """
    import argparse
    import importlib
    import json
    import subprocess
    import sys
    from pathlib import Path


    def _all_text(repo_root: Path) -> str:
        chunks = []
        for file_path in sorted(repo_root.rglob("*")):
            if not file_path.is_file():
                continue
            try:
                chunks.append(file_path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                continue
        return "\\n".join(chunks)


    def _run_probe(probe: dict[str, object], repo_root: Path) -> dict[str, object]:
        kind = str(probe["kind"])
        detail = ""
        passed = False

        if kind == "path_absent":
            relative_path = Path(str(probe["path"]))
            passed = not (repo_root / relative_path).exists()
            detail = f"Expected {relative_path} to be absent."
        elif kind == "path_present":
            relative_path = Path(str(probe["path"]))
            passed = (repo_root / relative_path).exists()
            detail = f"Expected {relative_path} to be present."
        elif kind in {"string_absent", "string_present"}:
            path = probe.get("path")
            target = str(probe["text"])
            if path is None:
                haystack = _all_text(repo_root)
            else:
                haystack = (repo_root / str(path)).read_text(encoding="utf-8")
            present = target in haystack
            passed = not present if kind == "string_absent" else present
            detail = f"Expected string {target!r} with kind {kind}."
        elif kind == "python_call":
            sys.path.insert(0, str(repo_root))
            module = importlib.import_module(str(probe["module"]))
            target = getattr(module, str(probe["callable"]))
            actual = target(*probe.get("args", []), **probe.get("kwargs", {}))
            expected = probe.get("expected")
            passed = actual == expected
            detail = f"Expected {expected!r}, got {actual!r}."
        elif kind == "command_success":
            completed = subprocess.run(
                str(probe["command"]),
                cwd=str(repo_root / str(probe.get("cwd", "."))),
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )
            passed = completed.returncode == 0
            detail = (completed.stdout + completed.stderr).strip()
        else:
            raise ValueError(f"Unsupported probe kind: {kind}")

        message = str(probe.get("message", "Probe passed." if passed else detail))
        if not passed and detail and detail not in message:
            message = f"{message} {detail}".strip()
        return {
            "probe_id": str(probe["probe_id"]),
            "passed": passed,
            "category": str(probe["category"]),
            "message": message,
            "weight": float(probe.get("weight", 1.0)),
            "failure_tags": [str(tag) for tag in probe.get("failure_tags", [])],
            "metadata": {"detail": detail},
        }


    def main() -> int:
        parser = argparse.ArgumentParser()
        parser.add_argument("--repo", required=True)
        args = parser.parse_args()
        task_dir = Path(__file__).resolve().parent
        checks = json.loads((task_dir / "checks.json").read_text(encoding="utf-8"))
        repo_root = Path(args.repo).resolve()
        payload = {"probes": [_run_probe(probe, repo_root) for probe in checks["probes"]]}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """
).strip() + "\n"


def _clean(text: str) -> str:
    return dedent(text).strip() + "\n"


def _prompt(instruction: str) -> str:
    return _clean(
        f"""
        {instruction}

        Requirements:
        - Remove the feature completely.
        - Do not leave placeholder stubs, fake deprecation notices, or "not implemented" paths.
        - Remove or update tests that only exist for the deleted feature.
        - Keep unrelated functionality working.
        - Clean up dead code, comments, docs, config, and flags related to the feature where appropriate.
        """
    )


def _pkg_init() -> str:
    return '"""Task microrepo package."""\n'


@dataclass(slots=True)
class GeneratedTask:
    task_id: str
    repo_name: str
    mode: str
    category: str
    difficulty: str
    instruction: str
    repo_files: dict[str, str]
    reference_files: dict[str, str]
    checks: list[dict[str, object]]
    residue_rules: dict[str, list[str]]


def _ui_task(task_id: str, repo_name: str, slug: str, label: str, event: str, difficulty: str) -> GeneratedTask:
    repo_files = {
        "app/__init__.py": _pkg_init(),
        "app/ui.py": _clean(
            f"""
            NAV_ITEMS = ["Dashboard", "{label}", "Settings"]
            MODALS = {{
                "{slug}": "{label} modal",
                "settings": "Settings panel",
            }}

            def nav_items() -> list[str]:
                return list(NAV_ITEMS)

            def has_modal(name: str) -> bool:
                return name in MODALS
            """
        ),
        f"app/{slug}.py": _clean(
            f"""
            TITLE = "{label}"
            DESCRIPTION = "{label} surface copy"
            """
        ),
        "app/analytics.py": _clean(
            f"""
            EVENTS = ["dashboard.opened", "settings.opened", "{event}"]

            def tracked_events() -> list[str]:
                return list(EVENTS)
            """
        ),
        "tests/test_ui.py": _clean(
            f"""
            import unittest

            from app.ui import has_modal, nav_items


            class UITests(unittest.TestCase):
                def test_feature_is_visible(self) -> None:
                    self.assertIn("{label}", nav_items())
                    self.assertTrue(has_modal("{slug}"))

                def test_settings_survives(self) -> None:
                    self.assertIn("Settings", nav_items())
                    self.assertTrue(has_modal("settings"))
            """
        ),
    }
    reference_files = {
        "app/__init__.py": _pkg_init(),
        "app/ui.py": _clean(
            """
            NAV_ITEMS = ["Dashboard", "Settings"]
            MODALS = {
                "settings": "Settings panel",
            }

            def nav_items() -> list[str]:
                return list(NAV_ITEMS)

            def has_modal(name: str) -> bool:
                return name in MODALS
            """
        ),
        "app/analytics.py": _clean(
            """
            EVENTS = ["dashboard.opened", "settings.opened"]

            def tracked_events() -> list[str]:
                return list(EVENTS)
            """
        ),
        "tests/test_ui.py": _clean(
            """
            import unittest

            from app.ui import has_modal, nav_items


            class UITests(unittest.TestCase):
                def test_settings_survives(self) -> None:
                    self.assertEqual(nav_items(), ["Dashboard", "Settings"])
                    self.assertTrue(has_modal("settings"))
            """
        ),
    }
    checks = [
        {
            "probe_id": f"{slug}_file_removed",
            "kind": "path_absent",
            "path": f"app/{slug}.py",
            "category": "removal_completeness",
            "message": f"The {label.lower()} module should be removed.",
            "failure_tags": ["under_deletion"],
        },
        {
            "probe_id": f"{slug}_copy_removed",
            "kind": "string_absent",
            "path": "app/ui.py",
            "text": label,
            "category": "removal_completeness",
            "message": f"The {label.lower()} UI copy should be removed.",
            "failure_tags": ["under_deletion"],
        },
        {
            "probe_id": f"{slug}_analytics_removed",
            "kind": "string_absent",
            "path": "app/analytics.py",
            "text": event,
            "category": "removal_completeness",
            "message": f"The {label.lower()} analytics event should be removed.",
            "failure_tags": ["under_deletion", "dead_residue"],
        },
        {
            "probe_id": f"{slug}_settings_survive",
            "kind": "python_call",
            "module": "app.ui",
            "callable": "nav_items",
            "expected": ["Dashboard", "Settings"],
            "category": "regression_safety",
            "message": "The surviving navigation items should still render.",
            "failure_tags": ["over_deletion"],
        },
    ]
    residue_rules = {
        "banned_patterns": ["Not implemented", "TODO.*remove", label, event],
        "forbidden_symbols": [event],
        "forbidden_paths": [f"app/{slug}.py"],
    }
    return GeneratedTask(
        task_id=task_id,
        repo_name=repo_name,
        mode="pure_deletion",
        category="ui_only_removal",
        difficulty=difficulty,
        instruction=f"Remove the {label.lower()} UI feature completely. Preserve dashboard and settings behavior.",
        repo_files=repo_files,
        reference_files=reference_files,
        checks=checks,
        residue_rules=residue_rules,
    )


def _module_task(
    *,
    task_id: str,
    repo_name: str,
    mode: str,
    category: str,
    difficulty: str,
    instruction: str,
    repo_files: dict[str, str],
    reference_files: dict[str, str],
    checks: list[dict[str, object]],
    residue_rules: dict[str, list[str]],
) -> GeneratedTask:
    return GeneratedTask(
        task_id=task_id,
        repo_name=repo_name,
        mode=mode,
        category=category,
        difficulty=difficulty,
        instruction=instruction,
        repo_files=repo_files,
        reference_files=reference_files,
        checks=checks,
        residue_rules=residue_rules,
    )


def build_task_specs() -> list[GeneratedTask]:
    tasks = [
        _ui_task("deletebench_001", "micro_feedback", "feedback", "Feedback", "feedback.opened", "easy"),
        _ui_task("deletebench_002", "micro_changelog", "changelog", "Changelog", "changelog.opened", "easy"),
        _ui_task("deletebench_003", "micro_export_ui", "export", "Export", "export.opened", "medium"),
    ]

    tasks.append(
        _module_task(
            task_id="deletebench_004",
            repo_name="micro_notifications",
            mode="deletion_with_repair",
            category="full_stack_feature_removal",
            difficulty="medium",
            instruction="Remove the email notifications feature completely. Preserve in-app notifications and shared mail formatting helpers.",
            repo_files={
                "app/__init__.py": _pkg_init(),
                "app/config.py": _clean(
                    """
                    EMAIL_NOTIFICATIONS_ENABLED = True
                    IN_APP_NOTIFICATIONS_ENABLED = True
                    """
                ),
                "app/mail.py": _clean(
                    """
                    def format_email(subject: str, body: str) -> str:
                        return f"Subject: {subject}\\n\\n{body}"
                    """
                ),
                "app/notifications.py": _clean(
                    """
                    from app.config import EMAIL_NOTIFICATIONS_ENABLED, IN_APP_NOTIFICATIONS_ENABLED

                    def available_channels() -> list[str]:
                        channels = []
                        if EMAIL_NOTIFICATIONS_ENABLED:
                            channels.append("email")
                        if IN_APP_NOTIFICATIONS_ENABLED:
                            channels.append("in_app")
                        return channels

                    def send_email_notification(user: str, message: str) -> str:
                        return f"email:{user}:{message}"

                    def send_in_app_notification(user: str, message: str) -> str:
                        return f"in_app:{user}:{message}"
                    """
                ),
                "app/worker.py": _clean(
                    """
                    from app.notifications import available_channels

                    def queued_jobs() -> list[str]:
                        jobs = []
                        if "email" in available_channels():
                            jobs.append("email_notifications")
                        if "in_app" in available_channels():
                            jobs.append("in_app_notifications")
                        return jobs
                    """
                ),
                "tests/test_notifications.py": _clean(
                    """
                    import unittest

                    from app.mail import format_email
                    from app.notifications import available_channels, send_email_notification, send_in_app_notification
                    from app.worker import queued_jobs


                    class NotificationTests(unittest.TestCase):
                        def test_email_notifications_exist(self) -> None:
                            self.assertIn("email", available_channels())
                            self.assertEqual(send_email_notification("lee", "hi"), "email:lee:hi")
                            self.assertIn("email_notifications", queued_jobs())

                        def test_in_app_survives(self) -> None:
                            self.assertIn("in_app", available_channels())
                            self.assertEqual(send_in_app_notification("lee", "hi"), "in_app:lee:hi")
                            self.assertEqual(format_email("hello", "body"), "Subject: hello\\n\\nbody")
                    """
                ),
            },
            reference_files={
                "app/__init__.py": _pkg_init(),
                "app/config.py": _clean(
                    """
                    IN_APP_NOTIFICATIONS_ENABLED = True
                    """
                ),
                "app/mail.py": _clean(
                    """
                    def format_email(subject: str, body: str) -> str:
                        return f"Subject: {subject}\\n\\n{body}"
                    """
                ),
                "app/notifications.py": _clean(
                    """
                    from app.config import IN_APP_NOTIFICATIONS_ENABLED

                    def available_channels() -> list[str]:
                        return ["in_app"] if IN_APP_NOTIFICATIONS_ENABLED else []

                    def send_in_app_notification(user: str, message: str) -> str:
                        return f"in_app:{user}:{message}"
                    """
                ),
                "app/worker.py": _clean(
                    """
                    from app.notifications import available_channels

                    def queued_jobs() -> list[str]:
                        return ["in_app_notifications"] if "in_app" in available_channels() else []
                    """
                ),
                "tests/test_notifications.py": _clean(
                    """
                    import unittest

                    from app.mail import format_email
                    from app.notifications import available_channels, send_in_app_notification
                    from app.worker import queued_jobs


                    class NotificationTests(unittest.TestCase):
                        def test_in_app_survives(self) -> None:
                            self.assertEqual(available_channels(), ["in_app"])
                            self.assertEqual(send_in_app_notification("lee", "hi"), "in_app:lee:hi")
                            self.assertEqual(queued_jobs(), ["in_app_notifications"])
                            self.assertEqual(format_email("hello", "body"), "Subject: hello\\n\\nbody")
                    """
                ),
            },
            checks=[
                {"probe_id": "email_flag_removed", "kind": "string_absent", "path": "app/config.py", "text": "EMAIL_NOTIFICATIONS_ENABLED", "category": "removal_completeness", "message": "The email notification flag should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "email_sender_removed", "kind": "string_absent", "path": "app/notifications.py", "text": "send_email_notification", "category": "removal_completeness", "message": "The email notification path should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "email_job_removed", "kind": "string_absent", "path": "app/worker.py", "text": "email_notifications", "category": "removal_completeness", "message": "The email worker job should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "in_app_survives", "kind": "python_call", "module": "app.notifications", "callable": "available_channels", "expected": ["in_app"], "category": "regression_safety", "message": "In-app notifications should still work.", "failure_tags": ["over_deletion"]},
                {"probe_id": "mail_helper_survives", "kind": "python_call", "module": "app.mail", "callable": "format_email", "args": ["subject", "body"], "expected": "Subject: subject\n\nbody", "category": "regression_safety", "message": "Shared mail helpers should still work.", "failure_tags": ["shared_abstraction_breakage"]},
            ],
            residue_rules={
                "banned_patterns": ["Not implemented", "TODO.*remove", "EMAIL_NOTIFICATIONS_ENABLED", "email_notifications"],
                "forbidden_symbols": ["send_email_notification", "EMAIL_NOTIFICATIONS_ENABLED"],
                "forbidden_paths": [],
            },
        )
    )

    tasks.append(
        _module_task(
            task_id="deletebench_005",
            repo_name="micro_reports",
            mode="deletion_with_repair",
            category="full_stack_feature_removal",
            difficulty="medium",
            instruction="Remove the CSV export feature completely. Preserve JSON export and report browsing.",
            repo_files={
                "app/__init__.py": _pkg_init(),
                "app/config.py": _clean("CSV_EXPORT_ENABLED = True\nJSON_EXPORT_ENABLED = True"),
                "app/reports.py": _clean(
                    """
                    from app.config import CSV_EXPORT_ENABLED, JSON_EXPORT_ENABLED

                    def export_formats() -> list[str]:
                        formats = []
                        if CSV_EXPORT_ENABLED:
                            formats.append("csv")
                        if JSON_EXPORT_ENABLED:
                            formats.append("json")
                        return formats

                    def export_csv(rows: list[dict[str, str]]) -> str:
                        return ",".join(rows[0].keys()) + "\\n" + ",".join(rows[0].values())

                    def export_json(rows: list[dict[str, str]]) -> list[dict[str, str]]:
                        return list(rows)
                    """
                ),
                "app/api.py": _clean(
                    """
                    from app.reports import export_formats

                    def available_routes() -> list[str]:
                        routes = ["/reports"]
                        if "csv" in export_formats():
                            routes.append("/reports/export/csv")
                        if "json" in export_formats():
                            routes.append("/reports/export/json")
                        return routes
                    """
                ),
                "tests/test_reports.py": _clean(
                    """
                    import unittest

                    from app.api import available_routes
                    from app.reports import export_csv, export_formats, export_json


                    class ReportTests(unittest.TestCase):
                        def test_csv_export_exists(self) -> None:
                            rows = [{"name": "ana", "score": "9"}]
                            self.assertIn("csv", export_formats())
                            self.assertEqual(export_csv(rows), "name,score\\nana,9")
                            self.assertIn("/reports/export/csv", available_routes())

                        def test_json_export_survives(self) -> None:
                            rows = [{"name": "ana", "score": "9"}]
                            self.assertIn("json", export_formats())
                            self.assertEqual(export_json(rows), rows)
                    """
                ),
            },
            reference_files={
                "app/__init__.py": _pkg_init(),
                "app/config.py": _clean("JSON_EXPORT_ENABLED = True"),
                "app/reports.py": _clean(
                    """
                    from app.config import JSON_EXPORT_ENABLED

                    def export_formats() -> list[str]:
                        return ["json"] if JSON_EXPORT_ENABLED else []

                    def export_json(rows: list[dict[str, str]]) -> list[dict[str, str]]:
                        return list(rows)
                    """
                ),
                "app/api.py": _clean(
                    """
                    from app.reports import export_formats

                    def available_routes() -> list[str]:
                        routes = ["/reports"]
                        if "json" in export_formats():
                            routes.append("/reports/export/json")
                        return routes
                    """
                ),
                "tests/test_reports.py": _clean(
                    """
                    import unittest

                    from app.api import available_routes
                    from app.reports import export_formats, export_json


                    class ReportTests(unittest.TestCase):
                        def test_json_export_survives(self) -> None:
                            rows = [{"name": "ana", "score": "9"}]
                            self.assertEqual(export_formats(), ["json"])
                            self.assertEqual(export_json(rows), rows)
                            self.assertEqual(available_routes(), ["/reports", "/reports/export/json"])
                    """
                ),
            },
            checks=[
                {"probe_id": "csv_flag_removed", "kind": "string_absent", "path": "app/config.py", "text": "CSV_EXPORT_ENABLED", "category": "removal_completeness", "message": "The CSV export flag should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "csv_export_removed", "kind": "string_absent", "path": "app/reports.py", "text": "export_csv", "category": "removal_completeness", "message": "The CSV export implementation should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "csv_route_removed", "kind": "string_absent", "path": "app/api.py", "text": "/reports/export/csv", "category": "removal_completeness", "message": "The CSV export route should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "json_survives", "kind": "python_call", "module": "app.reports", "callable": "export_formats", "expected": ["json"], "category": "regression_safety", "message": "JSON export should still work.", "failure_tags": ["over_deletion"]},
            ],
            residue_rules={
                "banned_patterns": ["Not implemented", "TODO.*remove", "CSV_EXPORT_ENABLED", "/reports/export/csv"],
                "forbidden_symbols": ["export_csv", "CSV_EXPORT_ENABLED"],
                "forbidden_paths": [],
            },
        )
    )

    tasks.append(
        _module_task(
            task_id="deletebench_006",
            repo_name="micro_team",
            mode="deletion_with_repair",
            category="full_stack_feature_removal",
            difficulty="hard",
            instruction="Remove the team invites feature completely. Preserve team member listing and counts.",
            repo_files={
                "app/__init__.py": _pkg_init(),
                "app/config.py": _clean("TEAM_INVITES_ENABLED = True"),
                "app/members.py": _clean("def list_members() -> list[str]:\n    return ['ana', 'lee']"),
                "app/invites.py": _clean(
                    """
                    from app.config import TEAM_INVITES_ENABLED

                    def invite_routes() -> list[str]:
                        return ["/team/invites"] if TEAM_INVITES_ENABLED else []

                    def create_invite(email: str) -> str:
                        return f"invite:{email}"
                    """
                ),
                "app/api.py": _clean(
                    """
                    from app.invites import invite_routes
                    from app.members import list_members

                    def available_routes() -> list[str]:
                        return ["/team/members", *invite_routes()]

                    def member_count() -> int:
                        return len(list_members())
                    """
                ),
                "tests/test_team.py": _clean(
                    """
                    import unittest

                    from app.api import available_routes, member_count
                    from app.invites import create_invite


                    class TeamTests(unittest.TestCase):
                        def test_invites_exist(self) -> None:
                            self.assertIn("/team/invites", available_routes())
                            self.assertEqual(create_invite("a@example.com"), "invite:a@example.com")

                        def test_members_survive(self) -> None:
                            self.assertEqual(member_count(), 2)
                    """
                ),
            },
            reference_files={
                "app/__init__.py": _pkg_init(),
                "app/members.py": _clean("def list_members() -> list[str]:\n    return ['ana', 'lee']"),
                "app/api.py": _clean(
                    """
                    from app.members import list_members

                    def available_routes() -> list[str]:
                        return ["/team/members"]

                    def member_count() -> int:
                        return len(list_members())
                    """
                ),
                "tests/test_team.py": _clean(
                    """
                    import unittest

                    from app.api import available_routes, member_count


                    class TeamTests(unittest.TestCase):
                        def test_members_survive(self) -> None:
                            self.assertEqual(available_routes(), ["/team/members"])
                            self.assertEqual(member_count(), 2)
                    """
                ),
            },
            checks=[
                {"probe_id": "invites_removed", "kind": "path_absent", "path": "app/invites.py", "category": "removal_completeness", "message": "The invites module should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "invite_flag_removed", "kind": "path_absent", "path": "app/config.py", "category": "removal_completeness", "message": "The invite flag should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "member_routes_survive", "kind": "python_call", "module": "app.api", "callable": "available_routes", "expected": ["/team/members"], "category": "regression_safety", "message": "Member routes should survive.", "failure_tags": ["over_deletion"]},
            ],
            residue_rules={
                "banned_patterns": ["Not implemented", "TODO.*remove", "TEAM_INVITES_ENABLED", "invite:"],
                "forbidden_symbols": ["create_invite", "TEAM_INVITES_ENABLED"],
                "forbidden_paths": ["app/invites.py", "app/config.py"],
            },
        )
    )

    for task_id, repo_name, flag_name, label in [
        ("deletebench_007", "micro_beta_dashboard", "ENABLE_BETA_DASHBOARD", "Beta Insights"),
        ("deletebench_008", "micro_audit_preview", "ENABLE_AUDIT_PREVIEW", "Audit Preview"),
    ]:
        tasks.append(
            _module_task(
                task_id=task_id,
                repo_name=repo_name,
                mode="pure_deletion",
                category="feature_flag_sunset",
                difficulty="medium",
                instruction=f"Remove the {label.lower()} feature flag completely, including flag plumbing and dead branches. Preserve the stable dashboard behavior.",
                repo_files={
                    "app/__init__.py": _pkg_init(),
                    "app/config.py": _clean(f"{flag_name} = True"),
                    "app/dashboard.py": _clean(
                        f"""
                        from app.config import {flag_name}

                        def dashboard_cards() -> list[str]:
                            cards = ["Overview", "Health"]
                            if {flag_name}:
                                cards.append("{label}")
                            return cards
                        """
                    ),
                    "tests/test_dashboard.py": _clean(
                        f"""
                        import unittest

                        from app.dashboard import dashboard_cards


                        class DashboardTests(unittest.TestCase):
                            def test_flagged_card_exists(self) -> None:
                                self.assertIn("{label}", dashboard_cards())
                        """
                    ),
                },
                reference_files={
                    "app/__init__.py": _pkg_init(),
                    "app/dashboard.py": _clean(
                        """
                        def dashboard_cards() -> list[str]:
                            return ["Overview", "Health"]
                        """
                    ),
                    "tests/test_dashboard.py": _clean(
                        """
                        import unittest

                        from app.dashboard import dashboard_cards


                        class DashboardTests(unittest.TestCase):
                            def test_surviving_cards(self) -> None:
                                self.assertEqual(dashboard_cards(), ["Overview", "Health"])
                        """
                    ),
                },
                checks=[
                    {"probe_id": f"{flag_name.lower()}_flag_removed", "kind": "path_absent", "path": "app/config.py", "category": "removal_completeness", "message": "The feature flag file should be removed.", "failure_tags": ["under_deletion"]},
                    {"probe_id": f"{flag_name.lower()}_branch_removed", "kind": "string_absent", "path": "app/dashboard.py", "text": label, "category": "removal_completeness", "message": "The flagged branch should be removed.", "failure_tags": ["under_deletion"]},
                    {"probe_id": f"{flag_name.lower()}_survives", "kind": "python_call", "module": "app.dashboard", "callable": "dashboard_cards", "expected": ["Overview", "Health"], "category": "regression_safety", "message": "Stable dashboard cards should survive.", "failure_tags": ["over_deletion"]},
                ],
                residue_rules={
                    "banned_patterns": ["Not implemented", "TODO.*remove", flag_name, label],
                    "forbidden_symbols": [flag_name],
                    "forbidden_paths": ["app/config.py"],
                },
            )
        )

    tasks.append(
        _module_task(
            task_id="deletebench_009",
            repo_name="micro_auth",
            mode="deletion_with_repair",
            category="shared_abstraction_pruning",
            difficulty="hard",
            instruction="Remove the SAML provider completely while preserving the shared authentication abstraction and the remaining providers.",
            repo_files={
                "app/__init__.py": _pkg_init(),
                "app/auth.py": _clean(
                    """
                    def _password(token: str) -> str:
                        return f"password:{token}"

                    def _oauth(token: str) -> str:
                        return f"oauth:{token}"

                    def _saml(token: str) -> str:
                        return f"saml:{token}"

                    PROVIDERS = {"password": _password, "oauth": _oauth, "saml": _saml}

                    def available_providers() -> list[str]:
                        return sorted(PROVIDERS)

                    def authenticate(provider: str, token: str) -> str:
                        return PROVIDERS[provider](token)
                    """
                ),
                "tests/test_auth.py": _clean(
                    """
                    import unittest

                    from app.auth import authenticate, available_providers


                    class AuthTests(unittest.TestCase):
                        def test_saml_exists(self) -> None:
                            self.assertIn("saml", available_providers())
                            self.assertEqual(authenticate("saml", "token"), "saml:token")

                        def test_surviving_providers(self) -> None:
                            self.assertEqual(authenticate("password", "token"), "password:token")
                            self.assertEqual(authenticate("oauth", "token"), "oauth:token")
                    """
                ),
            },
            reference_files={
                "app/__init__.py": _pkg_init(),
                "app/auth.py": _clean(
                    """
                    def _password(token: str) -> str:
                        return f"password:{token}"

                    def _oauth(token: str) -> str:
                        return f"oauth:{token}"

                    PROVIDERS = {"password": _password, "oauth": _oauth}

                    def available_providers() -> list[str]:
                        return sorted(PROVIDERS)

                    def authenticate(provider: str, token: str) -> str:
                        return PROVIDERS[provider](token)
                    """
                ),
                "tests/test_auth.py": _clean(
                    """
                    import unittest

                    from app.auth import authenticate, available_providers


                    class AuthTests(unittest.TestCase):
                        def test_surviving_providers(self) -> None:
                            self.assertEqual(available_providers(), ["oauth", "password"])
                            self.assertEqual(authenticate("password", "token"), "password:token")
                            self.assertEqual(authenticate("oauth", "token"), "oauth:token")
                    """
                ),
            },
            checks=[
                {"probe_id": "saml_removed", "kind": "string_absent", "path": "app/auth.py", "text": "saml", "category": "removal_completeness", "message": "The SAML provider should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "providers_survive", "kind": "python_call", "module": "app.auth", "callable": "available_providers", "expected": ["oauth", "password"], "category": "regression_safety", "message": "The surviving providers should still be registered.", "failure_tags": ["shared_abstraction_breakage"]},
            ],
            residue_rules={
                "banned_patterns": ["Not implemented", "TODO.*remove", "saml"],
                "forbidden_symbols": ["saml"],
                "forbidden_paths": [],
            },
        )
    )

    tasks.append(
        _module_task(
            task_id="deletebench_010",
            repo_name="micro_notifiers",
            mode="deletion_with_repair",
            category="shared_abstraction_pruning",
            difficulty="medium",
            instruction="Remove the Slack notifier provider completely while preserving the notifier abstraction and the remaining providers.",
            repo_files={
                "app/__init__.py": _pkg_init(),
                "app/notifiers.py": _clean(
                    """
                    def email(payload: str) -> str:
                        return f"email:{payload}"

                    def webhook(payload: str) -> str:
                        return f"webhook:{payload}"

                    def slack(payload: str) -> str:
                        return f"slack:{payload}"

                    PROVIDERS = {"email": email, "webhook": webhook, "slack": slack}

                    def available_providers() -> list[str]:
                        return sorted(PROVIDERS)

                    def notify(provider: str, payload: str) -> str:
                        return PROVIDERS[provider](payload)
                    """
                ),
                "tests/test_notifiers.py": _clean(
                    """
                    import unittest

                    from app.notifiers import available_providers, notify


                    class NotifierTests(unittest.TestCase):
                        def test_slack_exists(self) -> None:
                            self.assertIn("slack", available_providers())
                            self.assertEqual(notify("slack", "ping"), "slack:ping")
                    """
                ),
            },
            reference_files={
                "app/__init__.py": _pkg_init(),
                "app/notifiers.py": _clean(
                    """
                    def email(payload: str) -> str:
                        return f"email:{payload}"

                    def webhook(payload: str) -> str:
                        return f"webhook:{payload}"

                    PROVIDERS = {"email": email, "webhook": webhook}

                    def available_providers() -> list[str]:
                        return sorted(PROVIDERS)

                    def notify(provider: str, payload: str) -> str:
                        return PROVIDERS[provider](payload)
                    """
                ),
                "tests/test_notifiers.py": _clean(
                    """
                    import unittest

                    from app.notifiers import available_providers, notify


                    class NotifierTests(unittest.TestCase):
                        def test_surviving_providers(self) -> None:
                            self.assertEqual(available_providers(), ["email", "webhook"])
                            self.assertEqual(notify("webhook", "ping"), "webhook:ping")
                    """
                ),
            },
            checks=[
                {"probe_id": "slack_removed", "kind": "string_absent", "path": "app/notifiers.py", "text": "slack", "category": "removal_completeness", "message": "The Slack provider should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "notifier_survives", "kind": "python_call", "module": "app.notifiers", "callable": "available_providers", "expected": ["email", "webhook"], "category": "regression_safety", "message": "Remaining providers should survive.", "failure_tags": ["shared_abstraction_breakage"]},
            ],
            residue_rules={
                "banned_patterns": ["Not implemented", "TODO.*remove", "slack"],
                "forbidden_symbols": ["slack"],
                "forbidden_paths": [],
            },
        )
    )

    tasks.append(
        _module_task(
            task_id="deletebench_011",
            repo_name="micro_parser",
            mode="deletion_with_repair",
            category="legacy_path_cleanup",
            difficulty="medium",
            instruction="Remove the legacy fallback parser completely and simplify the surviving parse path.",
            repo_files={
                "app/__init__.py": _pkg_init(),
                "app/parser.py": _clean(
                    """
                    def strict_parse(data: str) -> dict[str, str]:
                        if ":" not in data:
                            raise ValueError("strict parser requires a colon")
                        key, value = data.split(":", 1)
                        if key != "id":
                            raise ValueError("strict parser expects the id key")
                        return {"id": value}

                    def legacy_parse(data: str) -> dict[str, str]:
                        return {"id": data.strip()}

                    def parse(data: str) -> dict[str, str]:
                        try:
                            return strict_parse(data)
                        except ValueError:
                            return legacy_parse(data)
                    """
                ),
                "tests/test_parser.py": _clean(
                    """
                    import unittest

                    from app.parser import parse


                    class ParserTests(unittest.TestCase):
                        def test_legacy_path_exists(self) -> None:
                            self.assertEqual(parse("42"), {"id": "42"})
                    """
                ),
            },
            reference_files={
                "app/__init__.py": _pkg_init(),
                "app/parser.py": _clean(
                    """
                    def strict_parse(data: str) -> dict[str, str]:
                        if ":" not in data:
                            raise ValueError("strict parser requires a colon")
                        key, value = data.split(":", 1)
                        if key != "id":
                            raise ValueError("strict parser expects the id key")
                        return {"id": value}

                    def parse(data: str) -> dict[str, str]:
                        return strict_parse(data)
                    """
                ),
                "tests/test_parser.py": _clean(
                    """
                    import unittest

                    from app.parser import parse


                    class ParserTests(unittest.TestCase):
                        def test_strict_path_survives(self) -> None:
                            self.assertEqual(parse("id:42"), {"id": "42"})
                    """
                ),
            },
            checks=[
                {"probe_id": "legacy_removed", "kind": "string_absent", "path": "app/parser.py", "text": "legacy_parse", "category": "removal_completeness", "message": "The legacy parser should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "fallback_removed", "kind": "string_absent", "path": "app/parser.py", "text": "except ValueError", "category": "removal_completeness", "message": "The fallback branch should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "strict_survives", "kind": "python_call", "module": "app.parser", "callable": "parse", "args": ["id:42"], "expected": {"id": "42"}, "category": "regression_safety", "message": "Strict parsing should still work.", "failure_tags": ["over_deletion"]},
            ],
            residue_rules={
                "banned_patterns": ["Not implemented", "TODO.*remove", "legacy_parse"],
                "forbidden_symbols": ["legacy_parse"],
                "forbidden_paths": [],
            },
        )
    )

    tasks.append(
        _module_task(
            task_id="deletebench_012",
            repo_name="micro_store",
            mode="deletion_with_repair",
            category="legacy_path_cleanup",
            difficulty="hard",
            instruction="Remove the cache layer completely and simplify the repository call graph without breaking lookups.",
            repo_files={
                "app/__init__.py": _pkg_init(),
                "app/store.py": _clean(
                    """
                    class Database:
                        def get_user(self, user_id: str) -> dict[str, str]:
                            return {"id": user_id, "name": "Ada"}

                    class Cache:
                        def __init__(self) -> None:
                            self._data: dict[str, dict[str, str]] = {}

                        def get(self, key: str) -> dict[str, str] | None:
                            return self._data.get(key)

                        def set(self, key: str, value: dict[str, str]) -> None:
                            self._data[key] = value

                    class UserRepository:
                        def __init__(self) -> None:
                            self.database = Database()
                            self.cache = Cache()

                        def get_user(self, user_id: str) -> dict[str, str]:
                            cached = self.cache.get(user_id)
                            if cached is not None:
                                return cached
                            user = self.database.get_user(user_id)
                            self.cache.set(user_id, user)
                            return user

                    def probe_lookup() -> dict[str, str]:
                        return UserRepository().get_user("9")
                    """
                ),
                "tests/test_store.py": _clean(
                    """
                    import unittest

                    from app.store import UserRepository


                    class StoreTests(unittest.TestCase):
                        def test_cache_exists(self) -> None:
                            repository = UserRepository()
                            self.assertEqual(repository.get_user("7")["name"], "Ada")
                            self.assertEqual(repository.cache.get("7"), {"id": "7", "name": "Ada"})
                    """
                ),
            },
            reference_files={
                "app/__init__.py": _pkg_init(),
                "app/store.py": _clean(
                    """
                    class Database:
                        def get_user(self, user_id: str) -> dict[str, str]:
                            return {"id": user_id, "name": "Ada"}

                    class UserRepository:
                        def __init__(self) -> None:
                            self.database = Database()

                        def get_user(self, user_id: str) -> dict[str, str]:
                            return self.database.get_user(user_id)

                    def probe_lookup() -> dict[str, str]:
                        return UserRepository().get_user("9")
                    """
                ),
                "tests/test_store.py": _clean(
                    """
                    import unittest

                    from app.store import probe_lookup


                    class StoreTests(unittest.TestCase):
                        def test_lookup_survives(self) -> None:
                            self.assertEqual(probe_lookup(), {"id": "9", "name": "Ada"})
                    """
                ),
            },
            checks=[
                {"probe_id": "cache_class_removed", "kind": "string_absent", "path": "app/store.py", "text": "class Cache", "category": "removal_completeness", "message": "The cache layer should be removed.", "failure_tags": ["under_deletion"]},
                {"probe_id": "cache_usage_removed", "kind": "string_absent", "path": "app/store.py", "text": "self.cache", "category": "removal_completeness", "message": "The repository should no longer depend on the cache layer.", "failure_tags": ["under_deletion"]},
                {"probe_id": "lookup_survives", "kind": "python_call", "module": "app.store", "callable": "probe_lookup", "expected": {"id": "9", "name": "Ada"}, "category": "regression_safety", "message": "User lookup should still work.", "failure_tags": ["over_deletion"]},
            ],
            residue_rules={
                "banned_patterns": ["Not implemented", "TODO.*remove", "class Cache", "self.cache"],
                "forbidden_symbols": ["self.cache"],
                "forbidden_paths": [],
            },
        )
    )

    return tasks


def _yaml_dump(rules: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for key, values in rules.items():
        lines.append(f"{key}:")
        for value in values:
            lines.append(f"  - {json.dumps(value)}")
    return "\n".join(lines).rstrip() + "\n"


def _write_files(base_dir: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        destination = base_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def _public_metadata(files: dict[str, str]) -> dict[str, object]:
    loc = sum(content.count("\n") + 1 for content in files.values())
    return {"languages": ["Python"], "frameworks": ["unittest"], "approx_loc": loc}


def generate_tasks(tasks_root: str | Path, *, force: bool = False) -> list[str]:
    root = Path(tasks_root)
    if root.exists() and force:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []
    for task in build_task_specs():
        task_dir = root / task.task_id
        if task_dir.exists() and not force:
            raise FileExistsError(f"Task directory already exists: {task_dir}")
        if task_dir.exists():
            shutil.rmtree(task_dir)
        (task_dir / "repo").mkdir(parents=True)
        (task_dir / "hidden_eval").mkdir(parents=True)
        _write_files(task_dir / "repo", task.repo_files)

        diff_stats = diff_snapshots(task.repo_files, task.reference_files)
        manifest = {
            "task_id": task.task_id,
            "repo_name": task.repo_name,
            "entry_commit": "generated-v0",
            "mode": task.mode,
            "category": task.category,
            "difficulty": task.difficulty,
            "instruction": task.instruction,
            "public_metadata": _public_metadata(task.repo_files),
            "hidden_eval": {
                "commands": {
                    "build": "python3 -m compileall app tests",
                    "test": "python3 -m unittest discover -s tests -p 'test_*.py'",
                },
                "removal_probes": [probe["probe_id"] for probe in task.checks if probe["category"] == "removal_completeness"],
                "regression_probes": [probe["probe_id"] for probe in task.checks if probe["category"] == "regression_safety"],
                "residue_checks": list(task.residue_rules.keys()),
                "eval_script": "hidden_eval/eval.py",
                "residue_rules": "hidden_eval/residue_rules.yaml",
                "reference_solution": "hidden_eval/reference_solution.json",
                "allowed_touched_files": diff_stats.files_changed,
                "touched_file_slack": 1,
                "added_lines_slack": 6,
            },
        }
        (task_dir / "task.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        (task_dir / "public_prompt.txt").write_text(_prompt(task.instruction), encoding="utf-8")
        (task_dir / "hidden_eval" / "eval.py").write_text(EVAL_SCRIPT, encoding="utf-8")
        (task_dir / "hidden_eval" / "checks.json").write_text(json.dumps({"probes": task.checks}, indent=2, sort_keys=True), encoding="utf-8")
        (task_dir / "hidden_eval" / "reference_solution.json").write_text(json.dumps({"files": task.reference_files}, indent=2, sort_keys=True), encoding="utf-8")
        (task_dir / "hidden_eval" / "residue_rules.yaml").write_text(_yaml_dump(task.residue_rules), encoding="utf-8")
        generated.append(task.task_id)
    return generated
