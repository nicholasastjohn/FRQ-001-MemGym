# 2026-10-25 upstream preflight evidence

This directory contains an executed installation and zero-cost validation run against untouched upstream commit `50b404e6ae4e1fcd453d3e07963eb3e6312cbded`. These are engineering validation results, **not** reproduced Figure 2b performance results.

- Full editable install `.[dev,eval,swe,memory-eval]`: exit 0; no fallback needed.
- Import tests: **4 passed**.
- Six release-critical suites: **67 passed**.
- Full `tests/unit/`: **298 passed, 4 skipped, 2 warnings**, reproduced with skip details. Three skips require `minisweagent`; one is an intentionally unrun real-LLM integration. The documentation's all-track baseline is 301 passed and 1 skipped.
- DR module help, memory registry, DR benchmark-runner help, and dependency consistency check: exit 0.
- Upstream tracked working tree: clean before and after.
- Model/API requests: **none**. No benchmark accuracy or Figure 2b scores were produced.

`commands.jsonl` records exact argv, working directory, UTC start/end time, exit code and log path. Each numbered log combines stdout/stderr with the command and timing. `requirements.freeze.txt` is the actual installed distribution freeze; its editable checkout path is a record of this machine, not a portable source reference. `summary.json` records the checks and deviations. `capture_runner.py` is the exact evidence runner used. `sha256.json` hashes every retained evidence file except itself.

Python 3.12.14; macOS 26.6.2 ARM64; iMac21,1; 8 logical CPUs; 8 GiB RAM. All subprocesses exclude inherited API-key variables. Package downloads used the network; these checks do not perform paid inference. Dataset and model smoke evidence are stored separately.
