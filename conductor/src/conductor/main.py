"""CLI entry point for Conductor.

Usage:
    conductor "实现用户登录功能"
    conductor --no-tmux "修复 auth.py 中的 bug"
    conductor --timeout 600 "重构数据库层"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from .orchestrator import Orchestrator
from .tmux_manager import TmuxManager


def _find_personas_dir() -> Path:
    """Find the personas directory relative to the package."""
    # Check relative to this file (in src/conductor/)
    pkg_dir = Path(__file__).parent
    candidates = [
        pkg_dir.parent.parent / "personas",  # src/conductor/../../personas
        Path.cwd() / "conductor" / "personas",
        Path.cwd() / "personas",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Cannot find personas/ directory. "
        "Run conductor from the project root or set --personas-dir."
    )


def _print_banner() -> None:
    """Print the Conductor banner."""
    banner = """
╔══════════════════════════════════════════════════╗
║  🎼 Conductor — Multi-Actor Orchestration Engine ║
║     Dev Scenario · Powered by Claude Agent SDK   ║
╚══════════════════════════════════════════════════╝
"""
    print(banner)


def _print_summary(state: "TaskState") -> None:
    """Print final execution summary."""
    from .state import TaskState

    elapsed = time.time() - state.created_at
    print(f"\n{'━' * 50}")
    print(f"📊 执行摘要")
    print(f"{'━' * 50}")
    print(f"  任务: {state.title}")
    print(f"  状态: {state.current_phase.value}")
    print(f"  复杂度: {state.complexity.value if state.complexity else 'N/A'}")
    print(f"  迭代次数: {state.iterations}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  Actor 总数: {len(state.completed_actors)}")

    if state.plan:
        done_steps = [s for s in state.plan.steps if s.status == "done"]
        total_steps = len(state.plan.steps)
        print(f"  计划步骤: {len(done_steps)}/{total_steps} 完成")

    if state.memory:
        print(f"\n📝 关键事件:")
        for entry in state.memory[-10:]:
            print(f"  {entry}")


async def _run(args: argparse.Namespace) -> int:
    """Async main runner."""
    task_description = args.task
    project_dir = Path(args.project_dir).resolve()
    personas_dir = Path(args.personas_dir).resolve() if args.personas_dir else _find_personas_dir()

    if not project_dir.exists():
        print(f"❌ 项目目录不存在: {project_dir}", file=sys.stderr)
        return 1

    if not personas_dir.exists():
        print(f"❌ Personas 目录不存在: {personas_dir}", file=sys.stderr)
        return 1

    # tmux setup
    tmux: TmuxManager | None = None
    if args.tmux and TmuxManager.is_available():
        tmux = TmuxManager(session_name=f"conductor-{int(time.time()) % 10000}")
        try:
            tmux.create_session()
            print("📺 tmux 分屏已创建")
        except RuntimeError as e:
            print(f"⚠️ tmux 创建失败，降级为纯文本模式: {e}")
            tmux = None

    # Create and run orchestrator
    orchestrator = Orchestrator(
        task_description=task_description,
        project_dir=project_dir,
        personas_dir=personas_dir,
        tmux=tmux,
        max_iterations=args.max_iterations,
        actor_timeout=args.timeout,
    )

    try:
        state = await orchestrator.run()
        _print_summary(state)
        return 0 if state.current_phase.value == "DONE" else 1
    except KeyboardInterrupt:
        print("\n\n⏹ 用户中断")
        return 130
    except Exception as e:
        print(f"\n❌ 执行失败: {e}", file=sys.stderr)
        return 1
    finally:
        if tmux and args.tmux_cleanup:
            tmux.kill()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="conductor",
        description="🎼 Conductor: Multi-Actor orchestration engine for Dev scenario",
    )

    parser.add_argument(
        "task",
        help="Task description (what you want to build/fix/refactor)",
    )

    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root directory (default: current directory)",
    )

    parser.add_argument(
        "--personas-dir",
        default=None,
        help="Path to personas/ directory (auto-detected if not set)",
    )

    parser.add_argument(
        "--tmux",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable/disable tmux split-screen (default: enabled)",
    )

    parser.add_argument(
        "--tmux-cleanup",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Kill tmux session on exit (default: keep)",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Actor timeout in seconds (default: 300)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max quality gate iterations (default: 3)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    _print_banner()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
