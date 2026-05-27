# Ansible Playbooks — How to Write & Use

Covers playbook structure, variable passing, Python invocation via `Ansible` class, output capture, and conventions used in Press.

---

## Directory

All playbooks live in:
```
press/playbooks/
```
357+ playbooks total. Each `.yml` file is a single-play playbook.

---

## Playbook Structure

**Always use roles.** Every playbook delegates to a role — tasks live in `press/playbooks/roles/<role_name>/tasks/main.yml`, never inline in the playbook file.

### Standard playbook structure

```yaml
---
- name: Setup Database Server
  hosts: all
  become: yes
  become_user: root
  gather_facts: yes          # set to 'no' if facts not needed (faster)
  roles:
    - role: essentials
    - role: mariadb
    - role: agent
    - role: node_exporter
```

The playbook file is just a header + role list. All actual tasks go in the role.

> **Do not put tasks inline in the playbook file.** Inline tasks are harder to test, can't be reused across playbooks, and make the playbook file a mixed-concern mess. Older playbooks in the repo do this — don't follow that pattern.

### 3. Playbook with variables

Variables passed from Python are available as top-level Ansible variables:

```yaml
---
- name: Configure Nginx Routing
  become: yes
  hosts: all
  vars:
    nginx_conf_path: "/home/frappe/agent/nginx/nginx.conf"   # default/fallback
  roles:
    - role: nginx_conf_changes_for_tcp_streaming
```

**Variables declared in `vars:` are defaults — Python-passed values override them.**

---

## Python Invocation

### Import

```python
from press.runner import Ansible
```

### Simple invocation (no variables)

```python
def fetch_keys(self):
    ansible = Ansible(playbook="keys.yml", server=self)
    play = ansible.run()
    # play is an AnsiblePlay doc
    if play.status == "Success":
        ...
```

### With variables

```python
ansible = Ansible(
    playbook="setup_server.yml",
    server=self,
    user=self._ssh_user(),      # default: "root"
    port=self._ssh_port(),      # default: 22
    variables={
        "server": self.name,
        "private_ip": self.private_ip,
        "agent_password": agent_password,
        "certificate_private_key": certificate.private_key,
        "workers": "2",
        **self.get_mount_variables(),   # dict unpacking supported
    },
)
play = ansible.run()
```

### Ansible class signature

```python
Ansible(
    server,           # Server/DatabaseServer/etc. doc — provides IP
    playbook,         # filename in press/playbooks/ (e.g. "setup.yml")
    user="root",      # SSH user
    variables=None,   # dict of extra vars
    port=22,          # SSH port
)
```

`server.ip` is used if set, otherwise `server.private_ip`. For hosts behind a bastion, SSH ProxyCommand is auto-configured.

---

## Output Capture — AnsibleCallback

Press uses a custom Ansible callback class (`AnsibleCallback` in `runner.py`) that intercepts events and writes to DB in real time:

| Event | Action |
|-------|--------|
| `v2_playbook_on_start` | Creates `AnsiblePlay` doc, status=Running |
| `v2_playbook_on_task_start` | Creates `AnsibleTask` doc |
| `v2_runner_on_ok` | Updates task: status=Success, stdout saved |
| `v2_runner_on_failed` | Updates task: status=Failure, stderr saved |
| `v2_runner_on_skipped` | Updates task: status=Skipped |
| `v2_runner_on_unreachable` | Updates task: status=Unreachable |
| `v2_playbook_on_stats` | Writes ok/changed/failed/skipped counts to `AnsiblePlay` |

Also calls `frappe.publish_realtime()` for live progress in the UI.

Special: when a task in the `user` role runs, the callback extracts the SSH public key from the result and saves it to the server doc.

---

## AnsiblePlay Doc

After `ansible.run()`, returns an `AnsiblePlay` doc:

```python
play.status    # "Success" or "Failure"
play.ok        # count of successful tasks
play.changed   # count of changed tasks
play.failures  # count of failed tasks
play.skipped
play.unreachable
```

Standard pattern in server setup methods:

```python
play = ansible.run()
self.reload()
if play.status == "Success":
    self.status = "Active"
else:
    self.status = "Broken"
    self.save()
```

---

## Writing a New Playbook

### Step 1 — Create the role

```
press/playbooks/roles/my_operation/tasks/main.yml
```

```yaml
---
- name: Do something
  command: echo "{{ my_variable }}"

- name: Restart service
  systemd:
    name: myservice
    state: restarted
```

### Step 2 — Create the playbook file (thin wrapper only)

```
press/playbooks/my_operation.yml
```

```yaml
---
- name: My Operation
  hosts: all
  become: yes
  become_user: root
  gather_facts: no
  roles:
    - role: my_operation
```

No tasks here. The playbook file is just a header and role reference.

### Step 3 — Invoke from Python

```python
def my_operation(self, my_variable):
    ansible = Ansible(
        playbook="my_operation.yml",
        server=self,
        variables={"my_variable": my_variable},
    )
    play = ansible.run()
    if play.status != "Success":
        log_error("My Operation Failed", server=self.name)
```

### Step 3 — Handle errors

Wrap in try/except for structured error logging:

```python
def my_operation(self):
    try:
        ansible = Ansible(playbook="my_operation.yml", server=self)
        play = ansible.run()
        if play.status == "Success":
            self.status = "Active"
        else:
            self.status = "Broken"
        self.save()
    except Exception:
        log_error("My Operation Exception", server=self.as_dict())
```

---

## Variable Conventions

| Pattern | Description |
|---------|------------|
| `"server": self.name` | Pass docname for agent config |
| `"private_ip": self.private_ip` | Network config |
| `"agent_password": ...` | Sensitive values (not logged to UI) |
| `"certificate_private_key": cert.private_key` | Multi-line values — quoted correctly |
| `**self.get_mount_variables()` | Dict spread for computed groups of vars |

**Important**: Values with newlines (private keys, certificates) are automatically quoted when passed as `extra_vars` so Ansible receives them correctly.

---

## gather_facts

- `gather_facts: yes` — needed when playbook/roles use `ansible_facts` (OS info, interfaces, etc.)
- `gather_facts: no` — skip for speed when facts aren't used (typical for targeted maintenance ops)

---

## Common Gotchas

1. **All playbooks use `hosts: all`** — the inventory is always a single host (the target server IP).
2. **`become_user: root`** — all Press playbooks run as root.
3. **Variable quoting** — Press passes all variables as CLI `extra_vars`. Multi-line values (private keys) are single-quoted in the CLI args.
4. **SSH key checking is disabled** — `HOST_KEY_CHECKING = False` is set globally in the `Ansible` class.
5. **Bastion routing** — `_get_ssh_proxy_command(server)` auto-adds ProxyCommand for private-network servers.
