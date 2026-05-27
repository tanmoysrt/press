# Press Jobs — Architecture & How to Write New Ones

`PressJob` is the system for running multi-step cloud infrastructure workflows entirely within Press (no agent involved). Used for server provisioning, VM migrations, disk resizes, proxy failovers, etc.

**Key distinction**: `AgentJob` → runs operations ON the server via the agent daemon. `PressJob` → runs operations ABOUT the server via cloud APIs + Ansible.

---

## Architecture

`PressJob` inherits from `WorkflowBuilder` (the Press Workflow Engine). Each job type is a Python class. The workflow engine handles:
- Async step-by-step execution
- State persistence between steps
- Retry on failure
- `on_success` / `on_failure` callbacks

---

## Job Registry

Jobs are registered in `_JOBS_REGISTRY` dict at module load time:

```python
# press/press/doctype/press_job/press_job.py

_JOBS_REGISTRY: dict[str, type[PressJob]] = {}

def _init_jobs_registry():
    from press.infrastructure.doctype.virtual_disk_resize.virtual_disk_resize import VirtualDiskResize
    from .create_server_job import CreateServerJob
    # ... 20+ more
    
    _JOBS_REGISTRY.update({
        "Create Server": CreateServerJob,
        "Resize Virtual Disk": VirtualDiskResize,
        # ...
    })
```

When a `PressJob` doc is inserted with `job_type = "Create Server"`, the class is swapped dynamically:

```python
def after_insert(self):
    self.__class__ = _JOBS_REGISTRY[self.job_type]
    self.start_workflow()
```

---

## PressJob Fields

- `job_type` — string key into `_JOBS_REGISTRY`
- `server` — link to server doc (Server / DatabaseServer / etc.)
- `server_type` — dynamic type for the link field
- `virtual_machine` — optional link to VirtualMachine
- `status` — Pending / Running / Success / Failure
- `arguments` — JSON string of input parameters

---

## Context Properties

Inside any job class method:

```python
self.server_doc         # the linked Server or DatabaseServer doc
self.virtual_machine_doc  # linked VirtualMachine (if set)
self.arguments_dict     # parsed dict from self.arguments JSON
self.kv                 # WorkflowKVStore — persist values between steps
self.steps              # steps from linked Press Workflow
```

---

## Defining a Job — @flow and @task

### @flow

Marks the main orchestration method. Must be named `execute`.

When called normally (testing): runs synchronously.
When called via `run_as_workflow()`: the workflow engine discovers all `self.*` task calls via AST inspection and enqueues them as separate async tasks.

### @task

Marks individual steps. Each `@task` is one step in the workflow.

```python
@task
def provision_server(self):
    machine = self.virtual_machine_doc
    if machine.status != "Draft":
        return   # idempotent guard
    machine.provision()

@task(queue="long", timeout=1200)  # long-running task
def wait_for_server(self):
    # polling with defer pattern
    machine = self.virtual_machine_doc
    if machine.status != "Running":
        self.defer_current_task()  # re-enqueues this step after delay
```

**Options on @task:**
- `queue="long"` — routes to long-running RQ queue
- `timeout=N` — seconds before task is killed

---

## Minimal Job Example

```python
from press.press.doctype.press_job.press_job import PressJob
from press.runner import flow, task

class MyInfraJob(PressJob):

    @flow
    def execute(self):
        self.step_one()
        self.step_two()
        self.step_three()

    @task
    def step_one(self):
        vm = self.virtual_machine_doc
        vm.do_something()
        self.kv.set("result", vm.instance_id)   # persist for next step

    @task(queue="long", timeout=600)
    def step_two(self):
        instance_id = self.kv.get("result")     # read from KV store
        # long work here
        if not self.check_ready():
            self.defer_current_task()            # retry this step

    @task
    def step_three(self):
        server = self.server_doc
        server.status = "Active"
        server.save()

    def on_press_job_success(self, workflow):
        """Called after all steps succeed."""
        server = self.server_doc
        server.notify_team()

    def on_press_job_failure(self, workflow):
        """Called when any step fails."""
        server = self.server_doc
        server.status = "Broken"
        server.save()
```

---

## Registering the Job

Add to `_init_jobs_registry()` in `press_job.py`:

```python
from press.press.doctype.my_infra_job.my_infra_job import MyInfraJob

_JOBS_REGISTRY.update({
    ...
    "My Infra Job": MyInfraJob,
})
```

---

## Creating a Job (Inserting)

```python
frappe.get_doc({
    "doctype": "Press Job",
    "job_type": "My Infra Job",
    "server": server_name,
    "server_type": "Server",
    "virtual_machine": vm_name,
    "arguments": json.dumps({
        "param1": "value1",
        "param2": 42,
    }),
}).insert()
```

`after_insert` swaps `__class__` to `MyInfraJob` and calls `start_workflow()` automatically.

---

## Blocking: Concurrent Job Guard

`before_insert` prevents inserting a new job on the same server if one is already Pending/Running:

```python
def before_insert(self):
    existing = frappe.db.exists("Press Job", {
        "server": self.server,
        "status": ("in", ["Pending", "Running"]),
    })
    if existing:
        frappe.throw(f"Job already running on {self.server}")
```

Design jobs to be idempotent (check state before acting) so re-runs are safe.

---

## Deferred Tasks (Polling Pattern)

For steps that need to wait for async cloud operations:

```python
@task(queue="long", timeout=1800)
def wait_for_snapshot(self):
    vm = self.virtual_machine_doc
    vm.sync()
    snapshot = frappe.get_doc("Virtual Disk Snapshot", self.kv.get("snapshot_name"))
    if snapshot.status != "Available":
        self.defer_current_task()   # re-enqueues after ~30s delay
```

---

## KV Store

Persist state between async steps:

```python
self.kv.set("key", value)   # WorkflowKVStore: persists to DB
value = self.kv.get("key")
```

For testing (in-memory only): uses `InMemoryKVStore`.

---

## Hooks

| Hook | Signature | When called |
|------|-----------|-------------|
| `on_press_job_success` | `(self, workflow)` | All steps completed successfully |
| `on_press_job_failure` | `(self, workflow)` | Any step failed (after retries exhausted) |

Both are optional. The workflow engine calls them via `on_workflow_success` / `on_workflow_failure` on the `PressJob` doc, which then calls your hook if defined.

---

## PressJob vs AgentJob — When to Use Which

| Concern | Use PressJob | Use AgentJob |
|---------|-------------|-------------|
| Cloud API calls (EC2, OCI) | ✓ | |
| Ansible playbooks on server | ✓ | |
| Operations inside bench filesystem | | ✓ |
| Running bench/site commands | | ✓ |
| Multi-step with async waits | ✓ (defer) | ✓ (steps) |
| Steps defined in Press | ✓ (@task) | ✓ (fixture) |
| Steps defined in agent | | ✓ (@step) |

---

## Real Example: CreateServerJob (simplified)

```python
class CreateServerJob(PressJob):

    @flow
    def execute(self):
        self.provision_server()
        self.wait_for_server_to_start()
        self.sync_virtual_machine()
        self.create_server_doc()
        self.setup_server_via_ansible()
        self.wait_for_setup_to_complete()
        # ... ~20 tasks total

    @task
    def provision_server(self):
        machine = self.virtual_machine_doc
        if machine.status != "Draft":
            return
        machine.provision()

    @task(queue="long", timeout=600)
    def wait_for_server_to_start(self):
        machine = self.virtual_machine_doc
        machine.sync()
        if machine.status != "Running":
            self.defer_current_task()

    @task
    def setup_server_via_ansible(self):
        server = self.server_doc
        server._setup_server()   # runs Ansible internally

    def on_press_job_success(self, _):
        server = self.server_doc
        server.is_provisioning_press_job_completed = 1
        server.save()

    def on_press_job_failure(self, _):
        server = self.server_doc
        server.status = "Broken"
        server.save()
```

---

## Key Files

| Purpose | Path |
|---------|------|
| PressJob base + registry | `press/press/doctype/press_job/press_job.py` |
| WorkflowBuilder base class | `press/workflow_engine/workflow_builder.py` |
| @flow / @task decorators | `press/runner.py` (or `workflow_engine`) |
| KV store | `press/workflow_engine/doctype/press_workflow_kv/` |
| Example: CreateServerJob | `press/press/doctype/press_job/create_server_job.py` |
| VirtualDiskResize job | `press/infrastructure/doctype/virtual_disk_resize/virtual_disk_resize.py` |
| VirtualMachineMigration job | `press/infrastructure/doctype/virtual_machine_migration/virtual_machine_migration.py` |
| ProxyFailover job | `press/press/doctype/proxy_failover/proxy_failover.py` |
