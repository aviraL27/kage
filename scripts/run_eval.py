"""Evaluation runner for Kage command-center tool calling accuracy.

Loads eval_dataset.json, passes test prompts through the LLM adapter with
the active system prompt and FastMCP tool schemas, and computes accuracy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kage.config import settings
from kage.llm.base import ChatMessage
from kage.llm.factory import get_llm
from kage.llm.prompt import get_system_prompt
from kage.mcp.client import mcp_client

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.WARNING)


async def run_evaluation(dataset_path: Optional[Path] = None) -> Dict[str, Any]:
    """Run full evaluation suite against the active LLM."""
    if dataset_path is None:
        dataset_path = ROOT_DIR / "eval" / "eval_dataset.json"

    with open(dataset_path, "r", encoding="utf-8") as f:
        test_cases: List[Dict[str, Any]] = json.load(f)

    llm = get_llm()
    tools_schema = await mcp_client.get_openai_tools()
    system_prompt = get_system_prompt()

    print("\n" + "=" * 70)
    print(" [*] KAGE AGENT TOOL-CALLING EVALUATION SUITE")
    print("=" * 70)
    print(f" LLM Provider   : {settings.llm_provider} ({llm.__class__.__name__})")
    print(f" Total Tests    : {len(test_cases)}")
    print(f" Tools Exposed  : {len(tools_schema)} via FastMCP")
    print("=" * 70 + "\n")

    results = []
    passed_count = 0
    total_latency_ms = 0.0

    for item in test_cases:
        test_id = item["id"]
        prompt = item["prompt"]
        expected_tool = item["expected_tool"]
        category = item.get("category", "general")

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=prompt),
        ]

        start_time = time.perf_counter()
        error_msg = None
        actual_tool = None
        tool_args = {}

        try:
            response = await llm.generate(messages=messages, tools=tools_schema)
            if response.tool_calls and len(response.tool_calls) > 0:
                actual_tool = response.tool_calls[0].name
                tool_args = response.tool_calls[0].arguments
            else:
                actual_tool = None
        except Exception as e:
            error_msg = str(e)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        total_latency_ms += latency_ms

        # Determine pass/fail
        passed = (actual_tool == expected_tool) and (error_msg is None)
        if passed:
            passed_count += 1
            status_symbol = "[PASS]"
        else:
            status_symbol = "[FAIL]"

        exp_str = expected_tool or "None (Direct reply)"
        act_str = actual_tool or "None (Direct reply)"
        if error_msg:
            act_str = f"ERROR: {error_msg}"

        print(
            f"[{test_id:02d}] {status_symbol} [{category:<9}] "
            f"Expected: {exp_str:<22} | Actual: {act_str:<22} "
            f"({latency_ms:.0f}ms)"
        )
        print(f"     Prompt: \"{prompt}\"")
        if tool_args:
            args_str = json.dumps(tool_args)
            if len(args_str) > 70:
                args_str = args_str[:67] + "..."
            print(f"     Args  : {args_str}")
        print("-" * 70)

        results.append({
            "id": test_id,
            "category": category,
            "prompt": prompt,
            "expected_tool": expected_tool,
            "actual_tool": actual_tool,
            "arguments": tool_args,
            "passed": passed,
            "latency_ms": round(latency_ms, 2),
            "error": error_msg,
        })

        # Throttle between calls to stay comfortably within free tier TPM limit
        await asyncio.sleep(3.0)

    total_count = len(test_cases)
    accuracy_pct = (passed_count / total_count) * 100.0 if total_count > 0 else 0.0
    avg_latency_ms = total_latency_ms / total_count if total_count > 0 else 0.0

    print("\n" + "=" * 70)
    print(" [*] EVALUATION SUMMARY")
    print("=" * 70)
    print(f" Passed          : {passed_count} / {total_count}")
    print(f" Accuracy        : {accuracy_pct:.1f}%")
    print(f" Avg Latency     : {avg_latency_ms:.1f}ms")
    print(f" Total Duration  : {(total_latency_ms / 1000.0):.2f}s")
    print("=" * 70 + "\n")

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": total_count,
        "passed": passed_count,
        "failed": total_count - passed_count,
        "accuracy_pct": round(accuracy_pct, 2),
        "avg_latency_ms": round(avg_latency_ms, 2),
        "results": results,
    }

    report_path = ROOT_DIR / "eval" / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Detailed evaluation report saved to: {report_path.relative_to(ROOT_DIR)}\n")
    return summary


if __name__ == "__main__":
    summary_res = asyncio.run(run_evaluation())
    if summary_res["accuracy_pct"] < 90.0:
        sys.exit(1)
    sys.exit(0)
