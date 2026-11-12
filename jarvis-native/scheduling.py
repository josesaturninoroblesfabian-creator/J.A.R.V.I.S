"""Scheduled jobs have independent history and a real native agent executor."""

import threading

from openjarvis.core.events import EventBus
from openjarvis.scheduler.scheduler import TaskScheduler
from openjarvis.scheduler.store import SchedulerStore


class ScheduleAdapter:
    def __init__(self, factory):
        self.factory = factory
        self.active = threading.Event()
        self.stopping = threading.Event()

    def ask(self, prompt, **_kwargs):
        if self.stopping.is_set():
            raise RuntimeError("Jarvis se está cerrando")
        self.active.set()
        brain = None
        try:
            brain = self.factory()
            brain.init(initialize_voice=False)
            brain._history.create()
            result = brain.ask(prompt)
            if isinstance(brain.last_error, str) and brain.last_error:
                raise RuntimeError(brain.last_error)
            return result
        finally:
            if brain:
                brain.close()
            self.active.clear()


class NativeSchedules:
    def __init__(self, path, factory, on_result=None):
        self.store = SchedulerStore(path)
        self.adapter = ScheduleAdapter(factory)
        self.bus = EventBus()
        if on_result:
            self.bus.subscribe("scheduler_task_end", lambda event: on_result(event.data))
        self.scheduler = TaskScheduler(
            self.store, system=self.adapter, bus=self.bus, poll_interval=5
        )
        self.scheduler.start()

    def create(self, prompt, seconds):
        if not prompt.strip():
            raise ValueError("Describe qué debe hacer Jarvis.")
        return self.scheduler.create_task(
            prompt.strip(),
            "interval",
            str(max(60, int(seconds))),
            agent="orchestrator",
        )

    def list(self):
        rows = []
        for task in self.scheduler.list_tasks():
            with self.scheduler._lock:
                logs = self.store.get_run_logs(task.id)
            rows.append((task, logs))
        return rows

    def toggle(self, identifier):
        task = next((t for t in self.scheduler.list_tasks() if t.id == identifier), None)
        if task is None:
            raise ValueError("Selecciona una tarea.")
        if task.status == "active":
            self.scheduler.pause_task(identifier)
        elif task.status == "paused":
            self.scheduler.resume_task(identifier)

    def close(self):
        self.adapter.stopping.set()
        self.scheduler.stop()
        self.store.close()
