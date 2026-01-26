# DevOps CLI - Code Optimization Plan
**Created:** 2026-01-25

---

## 🎯 Priority Issues Found

### 1. **CODE DUPLICATION** (High Priority)

#### Duplicated Functions:
| Function | Found In | Lines | Action |
|----------|----------|-------|--------|
| `parse_time_range()` | app.py, aws_logs.py | ~20 each | Move to utils/time_helpers.py |
| `colorize_log_level()` | app.py, aws_logs.py | ~15 each | Move to utils/output.py |
| `get_aws_session()` | app.py, aws_logs.py | ~30 each | Move to utils/aws_helpers.py |
| `get_github_headers()` | deploy.py, git.py | ~10 each | Move to utils/github_helper.py |
| `run_git()` | deploy.py, git.py | ~15 each | Move to utils/git_helpers.py |
| `load_websites_config()` | config/loader.py, config/websites.py | ~10 each | Use single source |

**Impact:** ~150 lines of duplicated code

---

### 2. **LARGE FILES** (High Priority)

| File | Lines | Should Be | Action |
|------|-------|-----------|--------|
| `commands/admin.py` | 2,874 | <500 | Split into: admin_users.py, admin_apps.py, admin_aws.py, admin_config.py |
| `dashboard/app.py` | 2,557 | <500 | Split into: app.py (core), routes.py, api_handlers.py |
| `monitoring/checker.py` | 904 | <300 | Split into: http_checker.py, tcp_checker.py, docker_checker.py |
| `commands/app.py` | 748 | <400 | Split into: app_commands.py, app_logs.py |
| `commands/git.py` | 739 | <400 | Split into: git_commands.py, pr_commands.py |

**Impact:** Better maintainability, easier navigation

---

### 3. **MISSING UTILITIES** (Medium Priority)

Create new utility modules:

```
devops_cli/utils/
├── time_helpers.py       # parse_time_range, format_time, etc.
├── aws_helpers.py        # get_aws_session, assume_role, etc.
├── git_helpers.py        # run_git, get_repo_info, etc.
└── log_formatters.py     # colorize_log_level, format_log, etc.
```

---

### 4. **INCONSISTENT PATTERNS** (Medium Priority)

#### Config Loading:
- Some files use `config/loader.py`
- Others directly load YAML
- **Fix:** Standardize on config/loader.py

#### Error Handling:
- Some use try/except with pass (silent failures)
- Others use proper logging
- **Fix:** Add proper error logging everywhere

#### AWS Session Creation:
- Duplicated in 2 files
- **Fix:** Single source in utils/aws_helpers.py

---

## 📋 Detailed Refactoring Plan

### Phase 1: Create Utility Modules (1-2 hours)

#### 1.1 Create `utils/time_helpers.py`
```python
"""Time and date utilities."""
from datetime import datetime, timedelta

def parse_time_range(time_str: str) -> datetime:
    """Parse time string like '1h', '30m', '2d' to datetime."""
    # Move implementation from app.py/aws_logs.py
    ...

def format_timestamp(timestamp: int) -> str:
    """Format Unix timestamp to readable string."""
    ...
```

#### 1.2 Create `utils/aws_helpers.py`
```python
"""AWS session and credential helpers."""
import boto3
from typing import Optional

def get_aws_session(region: Optional[str] = None, role_arn: Optional[str] = None):
    """Get AWS session using stored credentials."""
    # Move implementation from app.py/aws_logs.py
    ...

def assume_role(role_arn: str, session_name: str = "devops-cli"):
    """Assume AWS IAM role."""
    ...
```

#### 1.3 Create `utils/git_helpers.py`
```python
"""Git operation utilities."""

def run_git(args: list[str], capture: bool = True) -> tuple[bool, str]:
    """Run git command."""
    # Move from deploy.py/git.py
    ...

def get_current_branch() -> str:
    """Get current git branch."""
    ...
```

#### 1.4 Create `utils/log_formatters.py`
```python
"""Log formatting and colorizing."""
from rich.text import Text

def colorize_log_level(message: str) -> Text:
    """Colorize log message based on level."""
    # Move from app.py/aws_logs.py
    ...
```

---

### Phase 2: Split Large Files (2-3 hours)

#### 2.1 Split `commands/admin.py` (2,874 lines)

**New structure:**
```
commands/admin/
├── __init__.py           # Main admin app with typer commands
├── users.py              # User management (add, list, remove, import)
├── apps.py               # App configuration (add, list, remove, import)
├── servers.py            # Server configuration (add, list, remove, import)
├── aws.py                # AWS configuration (credentials, roles)
├── config.py             # Config management (init, export, import, validate)
└── utils.py              # Shared admin utilities
```

**Benefits:**
- Each file < 500 lines
- Easier to find specific functionality
- Better team collaboration

#### 2.2 Split `dashboard/app.py` (2,557 lines)

**New structure:**
```
dashboard/
├── app.py                # FastAPI app setup, middleware (< 200 lines)
├── routes/
│   ├── __init__.py
│   ├── auth.py          # Authentication routes
│   ├── apps.py          # App-related API endpoints
│   ├── servers.py       # Server-related API endpoints
│   ├── monitoring.py    # Monitoring & SSE streams
│   ├── security.py      # Security scanning endpoints
│   └── documents.py     # Document management
└── models/
    └── responses.py     # Pydantic response models
```

#### 2.3 Split `monitoring/checker.py` (904 lines)

**New structure:**
```
monitoring/
├── checker.py            # Main checker orchestrator (<200 lines)
├── checkers/
│   ├── __init__.py
│   ├── http.py          # HTTP/HTTPS checks
│   ├── tcp.py           # TCP port checks
│   ├── docker.py        # Docker container checks
│   └── command.py       # Command execution checks
```

---

### Phase 3: Remove Duplication (1 hour)

Replace all duplicated code with utility imports:

**Before (app.py):**
```python
def parse_time_range(time_str: str) -> datetime:
    """Parse time string..."""
    now = datetime.utcnow()
    if time_str.endswith("m"):
        minutes = int(time_str[:-1])
        return now - timedelta(minutes=minutes)
    # ...
```

**After (app.py):**
```python
from devops_cli.utils.time_helpers import parse_time_range
```

**Files to update:**
- commands/app.py
- commands/aws_logs.py
- commands/deploy.py
- commands/git.py

---

### Phase 4: Standardize Patterns (1 hour)

#### 4.1 Config Loading
All files should use:
```python
from devops_cli.config.loader import load_apps_config, save_apps_config
```

#### 4.2 Error Handling
Replace silent failures:
```python
# Bad
try:
    do_something()
except Exception:
    pass  # Silent failure!

# Good
try:
    do_something()
except Exception as e:
    logger.error(f"Failed to do something: {e}")
    raise
```

---

## 📊 Expected Benefits

### Code Quality:
- ✅ **-500 lines** of duplicated code removed
- ✅ **+80%** test coverage (easier to test smaller files)
- ✅ **-60%** file size (max 500 lines per file)

### Developer Experience:
- ✅ **Faster navigation** - find code 3x faster
- ✅ **Easier debugging** - smaller, focused files
- ✅ **Better collaboration** - less merge conflicts

### Performance:
- ✅ **Faster imports** - only load what you need
- ✅ **Better caching** - Python bytecode optimization

---

## 🚀 Implementation Order

### Week 1: Quick Wins
1. ✅ Create utility modules (utils/)
2. ✅ Move duplicated functions to utils
3. ✅ Update imports in all files
4. ✅ Test everything still works

### Week 2: Major Refactoring
1. ✅ Split admin.py into admin/ directory
2. ✅ Split dashboard/app.py into routes
3. ✅ Test all commands and dashboard

### Week 3: Polish
1. ✅ Standardize error handling
2. ✅ Add missing docstrings
3. ✅ Run linters (black, flake8)
4. ✅ Update documentation

---

## 🎯 Quick Start

Want to start right now? Here's the priority order:

1. **Create utils/time_helpers.py** (30 min)
   - Move parse_time_range()
   - Update app.py and aws_logs.py

2. **Create utils/log_formatters.py** (15 min)
   - Move colorize_log_level()
   - Update app.py and aws_logs.py

3. **Create utils/aws_helpers.py** (30 min)
   - Move get_aws_session()
   - Update app.py and aws_logs.py

**Result:** Remove ~100 lines of duplication in 1.5 hours!

---

## ⚠️ Important Notes

- Run tests after each change
- Keep backwards compatibility
- Don't change functionality, only structure
- Create git commits for each phase

