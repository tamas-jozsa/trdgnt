# Mage Build Tool

[Mage](https://magefile.org/) is a modern Make-like build tool using Go syntax.

## Installation

```bash
# macOS
brew install mage

# Or with Go
go install github.com/magefile/mage@latest
```

## Why Mage over Make?

### 1. Parameterized Commands
```bash
# Make: Need separate targets for each worker count
make trading-parallel    # 2 workers
make trading-parallel-3  # 3 workers

# Mage: Single command with parameter
mage trading:parallel 2  # 2 workers
mage trading:parallel 3  # 3 workers
mage trading:parallel 4  # 4 workers
```

### 2. Automatic Conda Environment Detection
The Magefile automatically detects and uses your `tradingagents` conda environment Python.

### 3. Type Safety
Mage tasks are Go functions - you get compile-time checking.

### 4. Better Error Handling
Proper error propagation and context cancellation.

### 5. Cross-Platform
Works the same on macOS, Linux, and Windows.

## Usage Examples

```bash
# Trading
mage trading:once                    # Single cycle
mage trading:dry                     # Dry run
mage trading:parallel 3              # 3 parallel workers
mage trading:force                   # Ignore checkpoint
mage trading:forceParallel 3         # Force + parallel
mage trading:from NVDA               # Resume from ticker
mage trading:ticker AAPL             # Analyze single ticker
mage trading:sync                    # Sync positions
mage trading:portfolio               # Show portfolio

# Research
mage research:run                    # Run daily research
mage research:force                  # Force research
mage research:dry                    # Dry run

# Analysis
mage analyze:ticker NVDA             # Analyze ticker
mage analyze:debug NVDA              # Debug mode
mage analyze:conviction              # Conviction dashboard
mage analyze:tierReview              # Monthly tier review

# Dashboard & Monitoring
mage dashboard                       # Start web dashboard
mage watch                           # Terminal dashboard
mage monitor:start                   # Start news monitor
mage monitor:stop                    # Stop news monitor
mage monitor:status                  # Check status

# Development
mage test                            # Run tests
mage lint                            # Run linter
mage format                          # Format code
mage clean                           # Clean cache
mage install                         # Install deps
mage update                          # Update deps
mage setup                           # Initial setup

# Utilities
mage info                            # Show project info
mage benchmark                       # Run benchmarks
mage ci                              # Run all CI checks
```

## List All Targets

```bash
mage -l
```

## Benefits Over Makefile

| Feature | Make | Mage |
|---------|------|------|
| Parameters | ❌ Limited | ✅ Full function params |
| Type Safety | ❌ None | ✅ Go compiler |
| Cross-Platform | ❌ Shell-dependent | ✅ Go standard lib |
| Error Handling | ❌ Exit codes only | ✅ Proper errors |
| Dependencies | ❌ Timestamps | ✅ Explicit deps |
| Documentation | ❌ Comments | ✅ Auto-generated |

## Keeping Both

The Makefile is kept for backward compatibility:
```bash
make trading-parallel-3   # Works
mage trading:parallel 3   # Also works
```
