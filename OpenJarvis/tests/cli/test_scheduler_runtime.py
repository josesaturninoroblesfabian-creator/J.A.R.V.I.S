from unittest.mock import MagicMock

from click.testing import CliRunner


def test_scheduler_start_wires_real_runtime_and_cleans_up(monkeypatch):
    import openjarvis.cli.scheduler_cmd as command
    import openjarvis.scheduler.scheduler as scheduler_module
    import openjarvis.system as system_module

    store = MagicMock()
    runtime = MagicMock()
    builder = MagicMock()
    builder.scheduler.return_value.build.return_value = runtime
    builder_type = MagicMock(return_value=builder)
    scheduler = MagicMock()
    scheduler_type = MagicMock(return_value=scheduler)
    monkeypatch.setattr(command, "_get_store", lambda: store)
    monkeypatch.setattr(system_module, "SystemBuilder", builder_type)
    monkeypatch.setattr(scheduler_module, "TaskScheduler", scheduler_type)
    monkeypatch.setattr(command.signal, "signal", MagicMock())

    def finish():
        raise SystemExit(0)

    monkeypatch.setattr(command.signal, "pause", finish, raising=False)
    result = CliRunner().invoke(command.scheduler, ["start", "--poll-interval", "7"])
    assert result.exit_code == 0, result.output
    builder.scheduler.assert_called_once_with(False)
    scheduler_type.assert_called_once_with(store, system=runtime, poll_interval=7)
    scheduler.start.assert_called_once()
    scheduler.stop.assert_called_once()
    runtime.close.assert_called_once()
    store.close.assert_called_once()
