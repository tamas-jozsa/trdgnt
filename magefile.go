//go:build mage
// +build mage

package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/magefile/mage/mg"
	"github.com/magefile/mage/sh"
)

// Default target to run when mage is called without arguments
var Default = Dashboard

// Project configuration
var (
	ProjectRoot = getProjectRoot()
	AppsDir     = filepath.Join(ProjectRoot, "apps")
	SrcDir      = filepath.Join(ProjectRoot, "src")
	PythonCmd   = getPythonCmd()
	CondaEnv    = "tradingagents"
)

func getProjectRoot() string {
	wd, _ := os.Getwd()
	return wd
}

func getPythonCmd() string {
	// Prefer conda environment Python
	condaPython := filepath.Join(os.Getenv("HOME"), "miniconda3", "envs", CondaEnv, "bin", "python")
	if runtime.GOOS == "windows" {
		condaPython = filepath.Join(os.Getenv("USERPROFILE"), "miniconda3", "envs", CondaEnv, "python.exe")
	}
	if _, err := os.Stat(condaPython); err == nil {
		return condaPython
	}
	// Fallback to python3 or python
	if _, err := exec.LookPath("python3"); err == nil {
		return "python3"
	}
	return "python"
}

// runPython executes a Python script with proper PYTHONPATH
func runPython(ctx context.Context, script string, args ...string) error {
	env := map[string]string{
		"PYTHONPATH": strings.Join([]string{ProjectRoot, AppsDir, SrcDir}, string(os.PathListSeparator)),
	}
	cmd := exec.CommandContext(ctx, PythonCmd, append([]string{filepath.Join(AppsDir, script)}, args...)...)
	cmd.Dir = ProjectRoot
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = os.Environ()
	for k, v := range env {
		cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
	}
	return cmd.Run()
}

// Trading namespace for trading-related tasks
type Trading mg.Namespace

// Once runs a single trading cycle
func (Trading) Once(ctx context.Context) error {
	mg.SerialDeps(Trading.Sync)
	fmt.Println("Running trading cycle...")
	return runPython(ctx, "trading_loop.py", "--once", "--no-wait")
}

// Dry runs trading cycle without placing orders
func (Trading) Dry(ctx context.Context) error {
	fmt.Println("Running dry-run (no orders)...")
	return runPython(ctx, "trading_loop.py", "--once", "--no-wait", "--dry-run")
}

// Parallel runs trading with N parallel workers (default: 2)
func (Trading) Parallel(ctx context.Context, workers int) error {
	if workers < 1 || workers > 4 {
		return fmt.Errorf("workers must be between 1 and 4, got %d", workers)
	}
	fmt.Printf("Running with %d parallel workers...\n", workers)
	return runPython(ctx, "trading_loop.py",
		"--parallel", strconv.Itoa(workers),
		"--once", "--no-wait")
}

// From resumes trading from a specific ticker
func (Trading) From(ctx context.Context, ticker string) error {
	fmt.Printf("Resuming from ticker: %s\n", ticker)
	return runPython(ctx, "trading_loop.py",
		"--once", "--no-wait",
		"--from", strings.ToUpper(ticker))
}

// Force runs trading cycle ignoring checkpoint
func (Trading) Force(ctx context.Context) error {
	fmt.Println("Force running (ignoring checkpoint)...")
	return runPython(ctx, "trading_loop.py", "--once", "--no-wait", "--force")
}

// ForceParallel force runs with parallel workers
func (Trading) ForceParallel(ctx context.Context, workers int) error {
	if workers < 1 || workers > 4 {
		return fmt.Errorf("workers must be between 1 and 4, got %d", workers)
	}
	fmt.Printf("Force running with %d parallel workers...\n", workers)
	return runPython(ctx, "trading_loop.py",
		"--parallel", strconv.Itoa(workers),
		"--once", "--no-wait", "--force")
}

// Ticker analyzes a single ticker
func (Trading) Ticker(ctx context.Context, ticker string) error {
	fmt.Printf("Analyzing single ticker: %s\n", ticker)
	return runPython(ctx, "trading_loop.py",
		"--once", "--no-wait",
		"--tickers", strings.ToUpper(ticker))
}

// Sync synchronizes positions from Alpaca
func (Trading) Sync(ctx context.Context) error {
	fmt.Println("Syncing positions from Alpaca...")
	return runPython(ctx, "update_positions.py")
}

// Portfolio shows current portfolio summary
func (Trading) Portfolio(ctx context.Context) error {
	return runPython(ctx, "alpaca_bridge.py", "--summary")
}

// Research namespace for research tasks
type Research mg.Namespace

// Run runs daily research (skips if already done)
func (Research) Run(ctx context.Context) error {
	fmt.Println("Running daily research...")
	return runPython(ctx, "daily_research.py")
}

// Force force-runs daily research (overwrites existing)
func (Research) Force(ctx context.Context) error {
	fmt.Println("Force running daily research...")
	return runPython(ctx, "daily_research.py", "--force")
}

// Dry prints research prompt without API call
func (Research) Dry(ctx context.Context) error {
	fmt.Println("Running research dry-run...")
	return runPython(ctx, "daily_research.py", "--dry-run")
}

// Analyze namespace for analysis tasks
type Analyze mg.Namespace

// Conviction runs conviction mismatch dashboard
func (Analyze) Conviction(ctx context.Context) error {
	return runPython(ctx, "analyze_conviction.py")
}

// TierReview runs monthly tier review
func (Analyze) TierReview(ctx context.Context) error {
	return runPython(ctx, "tier_manager.py")
}

// Ticker analyzes single ticker without orders
func (Analyze) Ticker(ctx context.Context, ticker string) error {
	fmt.Printf("Analyzing ticker (no orders): %s\n", ticker)
	return runPython(ctx, "single_ticker.py", "--ticker", strings.ToUpper(ticker))
}

// Debug analyzes ticker with debug output
func (Analyze) Debug(ctx context.Context, ticker string) error {
	fmt.Printf("Analyzing ticker with debug: %s\n", ticker)
	return runPython(ctx, "single_ticker.py", "--ticker", strings.ToUpper(ticker), "--debug")
}

// Dashboard starts the web dashboard
func Dashboard(ctx context.Context) error {
	fmt.Println("Starting dashboard on http://localhost:8888...")
	env := map[string]string{
		"PYTHONPATH": strings.Join([]string{ProjectRoot, AppsDir, SrcDir}, string(os.PathListSeparator)),
	}
	cmd := exec.CommandContext(ctx, "uvicorn", "dashboard.backend.main:app", "--reload", "--port", "8888")
	cmd.Dir = ProjectRoot
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = os.Environ()
	for k, v := range env {
		cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
	}
	return cmd.Run()
}

// Watch starts live terminal dashboard
func Watch(ctx context.Context) error {
	return sh.RunV("bash", filepath.Join(ProjectRoot, "scripts", "watch_agent.sh"))
}

// Monitor namespace for news monitor tasks
type Monitor mg.Namespace

// Start starts the news monitor
func (Monitor) Start(ctx context.Context) error {
	return runPython(ctx, "-c", "from news_monitor import NewsMonitor; m = NewsMonitor(); m.start(); print('News monitor started')")
}

// Stop stops the news monitor
func (Monitor) Stop(ctx context.Context) error {
	return runPython(ctx, "-c", "from news_monitor import NewsMonitor; m = NewsMonitor(); m.stop(); print('News monitor stopped')")
}

// Status checks news monitor status
func (Monitor) Status(ctx context.Context) error {
	return runPython(ctx, "-c", "from news_monitor import NewsMonitor; m = NewsMonitor(); print(m.get_status())")
}

// Test runs all tests
func Test(ctx context.Context) error {
	return sh.RunV(PythonCmd, "-m", "pytest", "tests/", "-v")
}

// TestQuick runs tests in quiet mode
func TestQuick(ctx context.Context) error {
	return sh.RunV(PythonCmd, "-m", "pytest", "tests/", "-q")
}

// Lint runs the linter
func Lint(ctx context.Context) error {
	return sh.RunV("ruff", "check", ".")
}

// Format formats code
func Format(ctx context.Context) error {
	return sh.RunV("ruff", "format", ".")
}

// Clean cleans Python cache files
func Clean(ctx context.Context) error {
	fmt.Println("Cleaning cache files...")
	dirs := []string{"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
	patterns := []string{"*.pyc", "*.pyo", "*.egg-info"}

	for _, dir := range dirs {
		_ = sh.Run("find", ".", "-type", "d", "-name", dir, "-exec", "rm", "-rf", "{}", "+")
	}
	for _, pattern := range patterns {
		_ = sh.Run("find", ".", "-name", pattern, "-delete")
	}
	fmt.Println("Cleaned!")
	return nil
}

// Install installs dependencies
func Install(ctx context.Context) error {
	fmt.Println("Installing dependencies...")
	return sh.RunV(PythonCmd, "-m", "pip", "install", "-e", ".[dev]")
}

// Update updates dependencies
func Update(ctx context.Context) error {
	fmt.Println("Updating dependencies...")
	return sh.RunV(PythonCmd, "-m", "pip", "install", "--upgrade", "-e", ".[dev]")
}

// Setup runs initial setup
func Setup(ctx context.Context) error {
	mg.SerialDeps(Install)
	fmt.Println("Creating .env file...")
	if _, err := os.Stat(".env"); os.IsNotExist(err) {
		sh.Copy("config/.env.example", ".env")
		fmt.Println("Created .env from config/.env.example - please edit it with your API keys!")
	}
	return nil
}

// CI runs all CI checks
func CI(ctx context.Context) error {
	mg.Deps(Lint)
	mg.Deps(Test)
	return nil
}

// Info prints project information
func Info(ctx context.Context) {
	fmt.Println("TradingAgents Project Info")
	fmt.Println("==========================")
	fmt.Printf("Project Root: %s\n", ProjectRoot)
	fmt.Printf("Python:       %s\n", PythonCmd)
	fmt.Printf("Conda Env:    %s\n", CondaEnv)
	fmt.Println("")
	fmt.Println("Available Commands:")
	fmt.Println("  mage trading:once           - Run single trading cycle")
	fmt.Println("  mage trading:dry            - Run dry-run (no orders)")
	fmt.Println("  mage trading:parallel 3     - Run with 3 parallel workers")
	fmt.Println("  mage trading:force          - Force run (ignore checkpoint)")
	fmt.Println("  mage trading:from NVDA      - Resume from ticker")
	fmt.Println("  mage trading:ticker AAPL    - Analyze single ticker")
	fmt.Println("  mage trading:sync           - Sync positions from Alpaca")
	fmt.Println("  mage trading:portfolio      - Show portfolio summary")
	fmt.Println("  mage research:run           - Run daily research")
	fmt.Println("  mage research:force         - Force research refresh")
	fmt.Println("  mage analyze:ticker NVDA    - Analyze single ticker (no orders)")
	fmt.Println("  mage dashboard              - Start web dashboard")
	fmt.Println("  mage watch                  - Start terminal dashboard")
	fmt.Println("  mage test                   - Run all tests")
	fmt.Println("  mage lint                   - Run linter")
	fmt.Println("  mage clean                  - Clean cache files")
	fmt.Println("  mage setup                  - Initial setup")
}

// Benchmark runs performance benchmarks
func Benchmark(ctx context.Context) error {
	fmt.Println("Running benchmarks...")
	start := time.Now()

	// Benchmark 1: Single ticker analysis
	fmt.Println("\n1. Single ticker analysis...")
	tickerStart := time.Now()
	if err := runPython(ctx, "single_ticker.py", "--ticker", "NVDA"); err != nil {
		fmt.Printf("   Error: %v\n", err)
	}
	fmt.Printf("   Time: %v\n", time.Since(tickerStart))

	// Benchmark 2: Position sync
	fmt.Println("\n2. Position sync...")
	syncStart := time.Now()
	if err := runPython(ctx, "update_positions.py"); err != nil {
		fmt.Printf("   Error: %v\n", err)
	}
	fmt.Printf("   Time: %v\n", time.Since(syncStart))

	fmt.Printf("\nTotal benchmark time: %v\n", time.Since(start))
	return nil
}
