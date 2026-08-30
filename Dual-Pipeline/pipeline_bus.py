"""
Pipeline Bus: Centralized Lifecycle & Real-Time Telemetry Dispatcher.
Formats high-visibility ANSI terminal logs and serializes NDJSON stream events.
"""

import json
import time
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Generator
from contextlib import contextmanager


class LifecycleState(str, Enum):
    ACTIVATED = "ACTIVATED"
    PROCESSING = "PROCESSING"
    DISPATCHING = "DISPATCHING"
    STANDBY = "STANDBY"
    FAULT = "FAULT"


class PipelineStage(str, Enum):
    INGEST_LIGHTING = "INGEST_LIGHTING"
    DOMAIN_ENGINE = "DOMAIN_ENGINE"
    SPATIAL_SCAFFOLD = "SPATIAL_SCAFFOLD"
    PROMPT_ENGINE = "PROMPT_ENGINE"
    VISION_PREPROCESSOR = "VISION_PREPROCESSOR"
    SYNTHESIS_ENGINE = "SYNTHESIS_ENGINE"
    ARCHIVER = "ARCHIVER"


STAGE_METADATA = {
    PipelineStage.INGEST_LIGHTING: {"idx": 1, "total": 7, "label": "Atmosphere & Ephemeris", "icon": "☀️"},
    PipelineStage.DOMAIN_ENGINE: {"idx": 2, "total": 7, "label": "Domain Engine (4 Mothers)", "icon": "🧠"},
    PipelineStage.SPATIAL_SCAFFOLD: {"idx": 3, "total": 7, "label": "Spatial Scaffold (7 Strata)", "icon": "🗺️"},
    PipelineStage.PROMPT_ENGINE: {"idx": 4, "total": 7, "label": "Prompt Compiler", "icon": "✍️"},
    PipelineStage.VISION_PREPROCESSOR: {"idx": 5, "total": 7, "label": "Vision Preprocessor (CUDA)", "icon": "⚡"},
    PipelineStage.SYNTHESIS_ENGINE: {"idx": 6, "total": 7, "label": "Synthesis Engine", "icon": "🎨"},
    PipelineStage.ARCHIVER: {"idx": 7, "total": 7, "label": "Archiver & Persistence", "icon": "💾"},
}

# ANSI Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_RED = "\033[31m"
C_GRAY = "\033[90m"


def format_ndjson(payload: Dict[str, Any]) -> str:
    """Encodes a payload dictionary as a newline-delimited JSON string chunk."""
    return json.dumps(payload) + "\n"


def emit_terminal_banner(session_info: str):
    """Prints the start banner for a pipeline run."""
    print(f"\n{C_CYAN}{'=' * 75}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN} [PIPELINE START]{C_RESET} {session_info}")
    print(f"{C_CYAN}{'=' * 75}{C_RESET}")


def emit_terminal_complete(total_latency_ms: float):
    """Prints the completion banner."""
    print(f"{C_CYAN}{'=' * 75}{C_RESET}")
    print(f"{C_BOLD}{C_GREEN} [PIPELINE COMPLETE]{C_RESET} Total Pipeline Latency: {C_BOLD}{total_latency_ms:.1f}ms{C_RESET}")
    print(f"{C_CYAN}{'=' * 75}{C_RESET}\n")


class StageScope:
    """Stateful handle yielded to the orchestrator to report milestone messages."""
    def __init__(self, stage: PipelineStage):
        self.stage = stage
        self.meta = STAGE_METADATA.get(stage, {"idx": 0, "total": 7, "label": stage.value, "icon": "⚙️"})
        self.start_time = time.perf_counter()

    def processing(self, message: str) -> str:
        idx, total, label = self.meta["idx"], self.meta["total"], self.meta["label"]
        print(f"  {C_YELLOW}⚙ PROCESSING {C_RESET} │ {message}")
        return format_ndjson({
            "type": "LIFECYCLE",
            "stage": self.stage.value,
            "stage_idx": idx,
            "total_stages": total,
            "label": label,
            "state": LifecycleState.PROCESSING.value,
            "message": message,
            "duration_ms": round((time.perf_counter() - self.start_time) * 1000.0, 1)
        })

    def dispatching(self, message: str) -> str:
        print(f"  {C_BLUE}▲ DISPATCHING{C_RESET} │ {message}")
        return format_ndjson({
            "type": "LIFECYCLE",
            "stage": self.stage.value,
            "stage_idx": self.meta["idx"],
            "total_stages": self.meta["total"],
            "label": self.meta["label"],
            "state": LifecycleState.DISPATCHING.value,
            "message": message,
            "duration_ms": round((time.perf_counter() - self.start_time) * 1000.0, 1)
        })

    def finish(self, summary: str = "") -> str:
        duration_ms = (time.perf_counter() - self.start_time) * 1000.0
        sec_str = f"{(duration_ms / 1000.0):.2f}s"
        print(f"  {C_GREEN}■ STANDBY    {C_RESET} │ {summary or 'Task completed'} {C_GRAY}───[IDLE / {sec_str}]{C_RESET}")
        return format_ndjson({
            "type": "LIFECYCLE",
            "stage": self.stage.value,
            "stage_idx": self.meta["idx"],
            "total_stages": self.meta["total"],
            "label": self.meta["label"],
            "state": LifecycleState.STANDBY.value,
            "message": summary or f"Completed in {sec_str}",
            "duration_ms": round(duration_ms, 1)
        })

    def fault(self, error_msg: str) -> str:
        duration_ms = (time.perf_counter() - self.start_time) * 1000.0
        print(f"  {C_RED}✖ FAULT      {C_RESET} │ {C_RED}{error_msg}{C_RESET} {C_GRAY}───[OFFLINE]{C_RESET}")
        return format_ndjson({
            "type": "LIFECYCLE",
            "stage": self.stage.value,
            "stage_idx": self.meta["idx"],
            "total_stages": self.meta["total"],
            "label": self.meta["label"],
            "state": LifecycleState.FAULT.value,
            "message": error_msg,
            "duration_ms": round(duration_ms, 1)
        })


def stage_activate(stage: PipelineStage, input_summary: str) -> tuple[StageScope, str]:
    """Announces activation and returns the scope handle + NDJSON string."""
    scope = StageScope(stage)
    idx, total, label, icon = scope.meta["idx"], scope.meta["total"], scope.meta["label"], scope.meta["icon"]
    print(f"\n{C_BOLD}[{idx}/{total}] {icon} {label.upper()}{C_RESET}")
    print(f"  {C_MAGENTA}▶ ACTIVATED  {C_RESET} │ {input_summary}")
    
    event_str = format_ndjson({
        "type": "LIFECYCLE",
        "stage": stage.value,
        "stage_idx": idx,
        "total_stages": total,
        "label": label,
        "state": LifecycleState.ACTIVATED.value,
        "message": input_summary,
        "duration_ms": 0.0
    })
    return scope, event_str