#!/usr/bin/env python3
"""GitHub Actions run watcher for pro-presenter-back-end.

Usage (from repo root):
  python .cursor/scripts/gha_watch.py
  python .cursor/scripts/gha_watch.py --sha f235d3e --wait 900

Optional: set GITHUB_TOKEN or GH_TOKEN for failed job log download (private logs).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

REPO = "EHWIYA/pro-presenter-back-end"
API = f"https://api.github.com/repos/{REPO}"
WORKFLOWS = ("CI", "Deploy NAS")


def _headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "pro-presenter-gha-watch",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url: str, timeout: int = 30) -> Any:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_text(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def git_head_sha() -> str:
    out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    return out


def runs_for_sha(sha: str, per_page: int = 15) -> list[dict[str, Any]]:
    data = _get(f"{API}/actions/runs?per_page={per_page}")
    return [r for r in data.get("workflow_runs", []) if r.get("head_sha", "").startswith(sha)]


def jobs_for_run(run_id: int) -> list[dict[str, Any]]:
    data = _get(f"{API}/actions/runs/{run_id}/jobs?per_page=20")
    return data.get("jobs", [])


def job_logs(job_id: int) -> str | None:
    try:
        return _get_text(f"{API}/actions/jobs/{job_id}/logs")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None
        raise


def classify(workflow: str, job: str, log: str | None) -> str:
    w, j = workflow.lower(), job.lower()
    if "deploy nas" in w or "ssh" in (log or "").lower() or "deploy.sh" in (log or "").lower():
        return "server"
    if workflow == "CI" and j in ("test", "publish"):
        return "backend"
    if workflow == "CI":
        return "backend"
    return "unknown"


def plan_for(bucket: str, workflow: str, job: str, log: str | None) -> list[str]:
    if bucket == "backend":
        return [
            "로컬: .\\.cursor\\scripts\\dev-test.ps1 로 pytest 재현",
            "실패 테스트·import·경로(api/) 수정 후 커밋",
            "CI 통과 후 publish(GHCR) 자동 진행 확인",
        ]
    if bucket == "server":
        return [
            "GHA Deploy NAS / appleboy/ssh-action 로그에서 SSH·deploy.sh 오류 확인",
            "NAS: ops/.env, docker compose, ghcr pull, bin/deploy.sh 수동 실행",
            "Secrets: NAS_HOST, NAS_USER, NAS_SSH_KEY, NAS_DEPLOY_PATH 점검",
            "현장: venues.json probe, PP API (docs/ENV.md)",
        ]
    if bucket == "both":
        return [
            "1) backend: CI test/publish 먼저 녹색으로",
            "2) server: Deploy NAS·NAS health·verse/send E2E",
            "3) 경계: API 응답 vs PP/NAS 네트워크 분리 재현",
        ]
    return ["워크플로·job 이름으로 bucket 재분류 후 docs/github-actions.md 참고"]


def wait_runs(sha: str, timeout_sec: int, poll_sec: int) -> dict[str, dict[str, Any]]:
    deadline = time.time() + timeout_sec
    found: dict[str, dict[str, Any]] = {}
    while time.time() < deadline:
        for r in runs_for_sha(sha):
            name = r.get("name")
            if name in WORKFLOWS:
                found[name] = r
        pending = [
            n
            for n in WORKFLOWS
            if n not in found or found[n].get("status") not in ("completed", "failure", "success")
        ]
        if len(found) >= 1 and not pending:
            # Deploy may be skipped; CI completed is enough to stop waiting
            ci = found.get("CI")
            if ci and ci.get("status") == "completed":
                deploy = found.get("Deploy NAS")
                if deploy and deploy.get("status") == "completed":
                    break
                if ci.get("conclusion") == "failure":
                    break
                if deploy is None and time.time() > deadline - poll_sec * 2:
                    # give deploy workflow time to appear
                    pass
                elif deploy and deploy.get("status") == "completed":
                    break
        if len(found) >= 2 and all(
            found.get(n, {}).get("status") == "completed" for n in found
        ):
            break
        time.sleep(poll_sec)
    return found


def report(sha: str, runs: dict[str, dict[str, Any]]) -> int:
    exit_code = 0
    print(f"## GHA report — {REPO}")
    print(f"- head: `{sha[:7]}` ({sha})")
    print()

    buckets: set[str] = set()
    for wf in WORKFLOWS:
        r = runs.get(wf)
        if not r:
            print(f"### {wf}\n- (no run found for this SHA yet)\n")
            continue
        status = r.get("status")
        conclusion = r.get("conclusion")
        url = r.get("html_url")
        icon = "OK" if conclusion == "success" else ("SKIP" if conclusion == "skipped" else "FAIL")
        if conclusion == "failure":
            exit_code = 1
        print(f"### {wf} — {icon}")
        print(f"- status: {status} / {conclusion}")
        print(f"- url: {url}")

        if conclusion != "failure":
            print()
            continue

        run_id = r["id"]
        for job in jobs_for_run(run_id):
            if job.get("conclusion") != "failure":
                continue
            jname = job.get("name", "?")
            log = job_logs(job["id"])
            bucket = classify(wf, jname, log)
            buckets.add(bucket)
            print(f"- failed job: **{jname}**")
            print(f"- classify: **{bucket}**")
            if log:
                tail = log.strip().splitlines()[-40:]
                print("- log (last 40 lines):")
                print("```")
                print("\n".join(tail))
                print("```")
            else:
                print("- log: (need GITHUB_TOKEN/GH_TOKEN for API log download)")
                print(f"- job url: {job.get('html_url')}")
            print()
            print("**Action plan:**")
            for i, step in enumerate(plan_for(bucket, wf, jname, log), 1):
                print(f"{i}. {step}")
            print()

    if len(buckets) > 1:
        print("### Overall classify: **both**")
        for i, step in enumerate(plan_for("both", "", "", None), 1):
            print(f"{i}. {step}")
    elif len(buckets) == 1:
        b = next(iter(buckets))
        print(f"### Overall classify: **{b}**")
    print()
    return exit_code


def main() -> int:
    p = argparse.ArgumentParser(description="Watch GHA runs for current or given SHA")
    p.add_argument("--sha", default="", help="commit SHA (default: HEAD)")
    p.add_argument("--wait", type=int, default=600, help="max seconds to poll")
    p.add_argument("--poll", type=int, default=20, help="poll interval seconds")
    p.add_argument("--no-wait", action="store_true", help="only report latest runs for SHA")
    args = p.parse_args()
    sha = args.sha or git_head_sha()
    if args.no_wait:
        runs = {r["name"]: r for r in runs_for_sha(sha) if r.get("name") in WORKFLOWS}
    else:
        print(f"Polling GHA for {sha[:7]} (up to {args.wait}s)...")
        runs = wait_runs(sha, args.wait, args.poll)
        if not runs:
            runs = {r["name"]: r for r in runs_for_sha(sha) if r.get("name") in WORKFLOWS}
    return report(sha, runs)


if __name__ == "__main__":
    sys.exit(main())
