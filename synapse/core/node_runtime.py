PROTOCOL_VERSION: str = "1.0"
"""NodeRuntime – simple in‑process node for testing (sync)."""
class NodeRuntime:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def execute(self, task):
        # Very naive capability check – assume all tasks succeed unless they are designed to fail.
        if task.get("action") == "write_file":
            raise Exception("Simulated write failure")
        # Return a deterministic result using task content
        return {"status": "completed", "node": self.node_id, "task": task, "checkpoint_id": "dummy-id"}
