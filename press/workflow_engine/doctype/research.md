# Workflow Engine DocType Group Research

This module implements a highly resilient, asynchronous, stateful in-house task execution and workflow orchestration engine inside the Press system.

## DocType Reference & Role

### [Press Workflow](press/press/workflow_engine/doctype/press_workflow/press_workflow.py)
- **Role**: The main process orchestrator and execution runner.
- **Workflow Execution Lifecycle**:
  - Enqueued automatically in the `after_insert` hook via `frappe.enqueue_doc()`.
  - Links to a controller inheriting from `WorkflowBuilder` (`linked_doctype`, `linked_docname`).
  - Dynamically runs the method defined in `main_method_name` with deserialized arguments (`args`, `kwargs`).
  - **Stdout Interception**: Wraps method execution in python's `redirect_stdout` context to capture and append console print statements to the `stdout` long text field.
  - **Asynchronous Waiting (Suspension)**: If a step enqueues a background job, it raises a custom `PressWorkflowTaskEnqueued` exception. The workflow runner cleanly exits, suspending the workflow in the `Queued` or `Running` state until the background job callback wakes it up.
  - **Error Pickling**: Captures standard python exceptions, serializing them into a `PressWorkflowObject` record. If another process calls `get_result()`, the engine automatically deserializes and re-raises the exact original exception to the caller.
  - **Exponential Backoff Callbacks**: On successful completion (`Success`) or hard failure (`Failure`), the engine enqueues callback handlers `on_workflow_success` or `on_workflow_failure`. If the callback raises an exception, the scheduler retries execution with exponential backoff delays ($2^{\text{attempts}}$ minutes) until it succeeds or exceeds `max_no_of_callback_attempts` (marking it `Fatal`).

### [Press Workflow Object](press/press/workflow_engine/doctype/press_workflow_object/press_workflow_object.py)
- **Role**: Acts as a state serializer/deserializer to pickle and store complex python runtime class instances, datatypes, and exceptions directly into the database.

### [Press Workflow Task](press/press/workflow_engine/doctype/press_workflow_task/press_workflow_task.py)
- **Role**: Represents a single unit of background work enqueued by the engine. Tracks execution and triggers the parent workflow wake-up when finished.

### [Press Workflow Step](press/press/workflow_engine/doctype/press_workflow_step/press_workflow_step.py)
- **Role**: Child table tracking individual task execution phases. Tracks step title, status (`Pending`, `Running`, `Success`, `Failure`, `Skipped`), start/end time, attempts, and traceback details.

### [Press Workflow KV](press/press/workflow_engine/doctype/press_workflow_kv/press_workflow_kv.py)
- **Role**: Implements a persistent, workflow-isolated Key-Value datastore interface (`WorkflowKVStore` vs `InMemoryKVStore`) to store runtime variables and state between asynchronous execution steps.

### [Press Workflow Test](press/press/workflow_engine/doctype/press_workflow_test/press_workflow_test.py)
- **Role**: A mock implementation of `WorkflowBuilder` used to test state changes, exceptions, callbacks, and step tracking.
