#!/usr/bin/env bash
# System specs and ROCm verification for local Pipecat voice agent.
# For AMD RX 6600 (gfx1050), set before running the agent:
#   export HSA_OVERRIDE_GFX_VERSION=10.3.0

set -e

echo "=== System summary ==="
echo "OS: $(uname -a)"
echo ""
echo "--- CPU ---"
if command -v lscpu &>/dev/null; then
  lscpu | grep -E "Model name|CPU\(s\):|Thread|Core"
else
  cat /proc/cpuinfo | grep -E "model name|cpu cores" | head -4
fi
echo ""
echo "--- Memory ---"
if command -v free &>/dev/null; then
  free -h
else
  cat /proc/meminfo | head -3
fi
echo ""
echo "--- GPU (from ROCm/AMD) ---"

ROCM_OK=0
if command -v rocm-smi &>/dev/null; then
  echo "rocm-smi:"
  if rocm-smi 2>/dev/null; then
    ROCM_OK=1
  else
    echo "  (rocm-smi failed - is ROCm installed and HSA_OVERRIDE_GFX_VERSION set for your GPU?)"
  fi
else
  echo "  rocm-smi not found."
  if command -v amd-smi &>/dev/null; then
    echo "amd-smi:"
    if amd-smi 2>/dev/null; then
      ROCM_OK=1
    else
      echo "  (amd-smi failed)"
    fi
  fi
fi

echo ""
echo "--- ROCm info (optional) ---"
if command -v rocminfo &>/dev/null; then
  if rocminfo 2>/dev/null; then
    ROCM_OK=1
  else
    echo "  rocminfo failed."
  fi
else
  echo "  rocminfo not found."
fi

echo ""
if [ "$ROCM_OK" = "1" ]; then
  echo "=== ROCm verification: OK ==="
else
  echo "=== ROCm verification: FAIL or not installed ==="
  echo "For AMD RX 6600 (gfx1050), use: export HSA_OVERRIDE_GFX_VERSION=10.3.0"
fi
