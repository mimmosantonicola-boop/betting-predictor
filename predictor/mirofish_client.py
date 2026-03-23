"""
predictor/mirofish_client.py

HTTP client that drives the full MiroFish simulation pipeline for a match.

Pipeline:
  1. POST /simulation/create   — create simulation record
  2. POST /simulation/prepare  — async: build knowledge graph + agent profiles
  3. (poll prepare/status)
  4. POST /simulation/start    — run multi-agent simulation
  5. (poll run-status)
  6. POST /report/generate     — generate prediction report
  7. (poll generate/status)
  8. GET  /report/{id}         — retrieve final markdown report
"""

from __future__ import annotations

import io
import os
import time
import logging
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_BASE = os.getenv("MIROFISH_API_URL", "http://localhost:5001")
_POLL_INTERVAL = 5   # seconds between status polls
_MAX_WAIT = 600      # 10 minutes max per stage


class SimulationError(Exception):
    pass


class MiroFishClient:
    """Controls MiroFish via its REST API."""

    def __init__(self, base_url: str = _DEFAULT_BASE):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    # ── Full pipeline ─────────────────────────────────────────────────────────

    def run_match_prediction(
        self,
        seed_text: str,
        prediction_prompt: str,
        match_label: str = "Match Prediction",
        simulation_rounds: int = 10,
    ) -> dict:
        """
        Execute the complete simulation → report pipeline.

        Returns a dict with:
          - simulation_id
          - report_id
          - report_markdown  (full text)
          - status  ("success" | "error")
          - error   (if status == "error")
        """
        try:
            # 1. Create
            logger.info("[MiroFish] Creating simulation: %s", match_label)
            sim_id = self._create_simulation(match_label)

            # 2. Upload seed material
            logger.info("[MiroFish] Uploading seed document...")
            self._upload_seed(sim_id, seed_text, match_label)

            # 3. Prepare (async)
            logger.info("[MiroFish] Preparing simulation (graph + profiles)...")
            task_id = self._start_prepare(sim_id, prediction_prompt)
            self._wait_for_task(
                task_id,
                poll_url=f"/simulation/prepare/status",
                task_key="task_id",
                label="Preparation",
            )

            # 4. Start simulation
            logger.info("[MiroFish] Starting simulation (%d rounds)...", simulation_rounds)
            self._start_simulation(sim_id, simulation_rounds)
            self._wait_for_simulation(sim_id)

            # 5. Generate report
            logger.info("[MiroFish] Generating prediction report...")
            task_id = self._start_report(sim_id)
            self._wait_for_task(
                task_id,
                poll_url="/report/generate/status",
                task_key="task_id",
                label="Report generation",
            )

            # 6. Fetch report
            report_id = self._get_report_id(sim_id)
            report_md = self._fetch_report(report_id)

            logger.info("[MiroFish] Pipeline complete.")
            return {
                "status": "success",
                "simulation_id": sim_id,
                "report_id": report_id,
                "report_markdown": report_md,
            }

        except SimulationError as e:
            logger.error("[MiroFish] Pipeline failed: %s", e)
            return {"status": "error", "error": str(e)}

    # ── Step implementations ──────────────────────────────────────────────────

    def _create_simulation(self, name: str) -> str:
        resp = self._post("/simulation/create", json={"name": name})
        sim_id = (
            resp.get("data", {}).get("simulation_id")
            or resp.get("data", {}).get("id")
            or resp.get("simulation_id")
        )
        if not sim_id:
            raise SimulationError(f"create returned no ID: {resp}")
        return str(sim_id)

    def _upload_seed(self, sim_id: str, text: str, filename: str) -> None:
        """Upload seed document as a text file."""
        fname = filename.replace(" ", "_")[:50] + ".txt"
        files = {"file": (fname, io.BytesIO(text.encode("utf-8")), "text/plain")}
        data = {"simulation_id": sim_id}
        resp = self._post_multipart("/simulation/upload", data=data, files=files)
        if not resp.get("success"):
            # Some versions attach the file to create directly — not fatal
            logger.warning("Upload endpoint returned: %s", resp)

    def _start_prepare(self, sim_id: str, prediction_prompt: str) -> str:
        resp = self._post("/simulation/prepare", json={
            "simulation_id": sim_id,
            "prediction_requirement": prediction_prompt,
        })
        task_id = (
            resp.get("data", {}).get("task_id")
            or resp.get("task_id")
        )
        if not task_id:
            raise SimulationError(f"prepare returned no task_id: {resp}")
        return str(task_id)

    def _wait_for_task(self, task_id: str, poll_url: str,
                        task_key: str, label: str) -> None:
        deadline = time.time() + _MAX_WAIT
        while time.time() < deadline:
            resp = self._post(poll_url, json={task_key: task_id})
            status = (
                resp.get("data", {}).get("status")
                or resp.get("status", "")
            )
            logger.info("[MiroFish] %s status: %s", label, status)
            if status in ("completed", "done", "finished", "success"):
                return
            if status in ("failed", "error"):
                raise SimulationError(f"{label} failed: {resp}")
            time.sleep(_POLL_INTERVAL)
        raise SimulationError(f"{label} timed out after {_MAX_WAIT}s")

    def _start_simulation(self, sim_id: str, rounds: int) -> None:
        resp = self._post("/simulation/start", json={
            "simulation_id": sim_id,
            "max_rounds": rounds,
        })
        if not resp.get("success"):
            raise SimulationError(f"start returned failure: {resp}")

    def _wait_for_simulation(self, sim_id: str) -> None:
        deadline = time.time() + _MAX_WAIT
        while time.time() < deadline:
            resp = self._get_req(f"/simulation/{sim_id}/run-status")
            status = (
                resp.get("data", {}).get("status")
                or resp.get("status", "")
            )
            logger.info("[MiroFish] Simulation status: %s", status)
            if status in ("completed", "finished", "stopped", "done"):
                return
            if status in ("failed", "error"):
                raise SimulationError(f"Simulation failed: {resp}")
            time.sleep(_POLL_INTERVAL)
        raise SimulationError(f"Simulation timed out after {_MAX_WAIT}s")

    def _start_report(self, sim_id: str) -> str:
        resp = self._post("/report/generate", json={"simulation_id": sim_id})
        task_id = (
            resp.get("data", {}).get("task_id")
            or resp.get("task_id")
        )
        if not task_id:
            raise SimulationError(f"report/generate returned no task_id: {resp}")
        return str(task_id)

    def _get_report_id(self, sim_id: str) -> str:
        resp = self._get_req(f"/report/by-simulation/{sim_id}")
        report_id = (
            resp.get("data", {}).get("id")
            or resp.get("data", {}).get("report_id")
            or resp.get("report_id")
        )
        if not report_id:
            raise SimulationError(f"Could not retrieve report ID for sim {sim_id}: {resp}")
        return str(report_id)

    def _fetch_report(self, report_id: str) -> str:
        resp = self._get_req(f"/report/{report_id}")
        content = (
            resp.get("data", {}).get("content")
            or resp.get("data", {}).get("markdown")
            or resp.get("content", "")
        )
        if not content:
            raise SimulationError(f"Empty report returned for {report_id}")
        return content

    # ── Utility ───────────────────────────────────────────────────────────────

    def _post(self, path: str, json: Optional[dict] = None) -> dict:
        try:
            resp = self.session.post(f"{self.base}{path}", json=json, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            raise SimulationError(f"POST {path} → HTTP {e.response.status_code}: {e.response.text[:200]}")
        except requests.RequestException as e:
            raise SimulationError(f"POST {path} failed: {e}")

    def _post_multipart(self, path: str, data: dict, files: dict) -> dict:
        try:
            resp = self.session.post(
                f"{self.base}{path}", data=data, files=files, timeout=30
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def _get_req(self, path: str, params: Optional[dict] = None) -> dict:
        try:
            resp = self.session.get(f"{self.base}{path}", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            raise SimulationError(f"GET {path} → HTTP {e.response.status_code}")
        except requests.RequestException as e:
            raise SimulationError(f"GET {path} failed: {e}")

    # ── Convenience: list existing simulations ────────────────────────────────

    def list_simulations(self) -> list[dict]:
        try:
            resp = self._get_req("/simulation/list")
            return resp.get("data", [])
        except SimulationError:
            return []
