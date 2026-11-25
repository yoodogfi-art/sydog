"""
research/registry.py  —  THE list of research command kinds.

Each kind becomes one Telegram command per instrument:
    suffix ""      -> /kr_govt
    suffix "_plot" -> /kr_govt_plot
    suffix "_z"    -> /kr_govt_z

TO ADD A NEW RESEARCH FEATURE
-----------------------------
1. Write research/commands/<feature>.py with
       def run(command, instrument, args) -> str | (png_bytes, caption)
   (use research.render.render_book for text replies — see commands/zscore.py)
2. Add one CommandKind line to COMMAND_KINDS below.
That's it: Telegram wiring and /help are generated from this list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# research/commands/sectors.py is intentionally not imported: equity is out of
# scope for now. Re-add it here and in COMMAND_KINDS to switch /sectors back on.
from research.commands import brief, forward, plot, query, spread, timeseries, zscore
from research.render import resolve_settings


def _always(command, instrument) -> bool:
    return True


def _is_curve(command, instrument) -> bool:
    """Curve charts need per-tenor columns.

    multi_row alone is not enough: a futures book is multi-row too, but its rows
    are 현재가 / 시장베이시스 / 이론베이시스 — there is no tenor axis to plot
    against. Such an instrument sets `curve: False` and gets no _plot command.
    """
    if "curve" in instrument:
        return bool(instrument["curve"])
    return resolve_settings(command, instrument)["multi_row"]


@dataclass
class CommandKind:
    suffix: str                       # appended to the instrument name
    run: Callable                     # (command, instrument, args) -> reply
    help: str                         # one line for /help
    applies_to: Callable = field(default=_always)   # (command, instrument) -> bool
    groups: bool = False              # also available on GROUPS (text replies only)
    error_word: str = "error"         # "[cmd] <error_word>: ..." on crashes
    fixed_name: str | None = None     # exact Telegram name, instead of instrument + suffix


COMMAND_KINDS: list[CommandKind] = [
    CommandKind("", query.run, groups=True,
                help="/<instrument> [6m | 20260115 20260216] - 스냅샷 / 기간 / 날짜범위"),
    CommandKind("_plot", plot.run, applies_to=_is_curve, error_word="plot error",
                help="/<instrument>_plot [4 28] - 커브 차트 (기본: 현재/1w/1mo/1y)"),
    CommandKind("_z", zscore.run, groups=True,
                help="/<instrument>_z [1y | all] - z-score / 백분위"),
    CommandKind("_ts", timeseries.run, error_word="chart error",
                help="/<instrument>_ts [5y] [3Y 10Y] - 시계열 차트"),
    CommandKind("", brief.run, fixed_name="brief", error_word="brief error",
                applies_to=lambda command, instrument: command == "kr_govt",
                help="/brief [1y|3y|all] [2.0] - 커브/스프레드/이례치 일일 브리프"),
    CommandKind("", spread.run, fixed_name="spread", error_word="spread error",
                applies_to=lambda command, instrument: command == "kr_govt",
                help="/spread [이름] [기간] [chart] - 크레딧/커브/국가간 스프레드"),
    CommandKind("", forward.run, fixed_name="forward", error_word="forward error",
                applies_to=lambda command, instrument: command == "kr_govt",
                help="/forward [20260115] - 국고채 커브 피팅 4종 + 선도금리 표"),
]


def run_group(kind: CommandKind, members, instruments, args) -> str:
    """Run a text command for every group member; one member failing never
    hides the others."""
    out = []
    for m in members:
        inst = instruments.get(m)
        if not inst:
            out.append(f"[{m}] unknown instrument")
            continue
        try:
            out.append(kind.run(m, inst, args))
        except FileNotFoundError:
            out.append(f"[{inst.get('label', m)}] file missing")
        except ValueError as e:
            out.append(str(e))
        except Exception as e:  # noqa: BLE001
            out.append(f"[{inst.get('label', m)}] error: {e}")
    return "\n".join(out)


def iter_commands(instruments: dict, groups: dict):
    """Yield (telegram_command, name, kind, target) for everything to register.
    name is the instrument/group name; target is ('instrument', instrument_dict)
    or ('group', member_list)."""
    for kind in COMMAND_KINDS:
        for name, inst in instruments.items():
            if kind.applies_to(name, inst):
                yield kind.fixed_name or name + kind.suffix, name, kind, ("instrument", inst)
        if kind.groups:
            for name, members in groups.items():
                yield name + kind.suffix, name, kind, ("group", members)
