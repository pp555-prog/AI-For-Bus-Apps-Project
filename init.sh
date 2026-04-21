#!/usr/bin/env bash
# =============================================================================
# NOCTURNE — Environment Bootstrap Script
# =============================================================================
# Run this once after cloning the repo to set up the development environment.
# Usage:
#   chmod +x init.sh
#   ./init.sh
#
# What it does:
#   1. Checks Python version (3.10+ required)
#   2. Creates a virtual environment (.venv)
#   3. Installs Python dependencies from requirements.txt
#   4. Copies .env.example → .env (if .env doesn't exist yet)
#   5. Verifies the backend can be imported without errors
# =============================================================================

set -e  # Exit on first error

echo ""
echo "======================================"
echo "  NOCTURNE — Environment Bootstrap"
echo "======================================"
echo ""

# -------------------------------------------------------------------
# 1. Python version check
# -------------------------------------------------------------------
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  echo "ERROR: Python not found. Install Python 3.10+ and retry."
  exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

echo "Python found: $PYTHON ($PY_VERSION)"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  echo "ERROR: Python 3.10+ required. Found $PY_VERSION."
  exit 1
fi

echo "Python version OK."
echo ""

# -------------------------------------------------------------------
# 2. Virtual environment
# -------------------------------------------------------------------
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)..."
  $PYTHON -m venv .venv
  echo "Virtual environment created."
else
  echo "Virtual environment already exists (.venv). Skipping creation."
fi

# Activate
if [ -f ".venv/Scripts/activate" ]; then
  # Windows (Git Bash / MSYS)
  source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
  # macOS / Linux
  source .venv/bin/activate
else
  echo "WARNING: Could not activate virtual environment automatically."
  echo "  Run manually: source .venv/bin/activate  (macOS/Linux)"
  echo "              or .venv\\Scripts\\activate    (Windows)"
fi

echo ""

# -------------------------------------------------------------------
# 3. Install dependencies
# -------------------------------------------------------------------
echo "Installing dependencies from requirements.txt..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "Dependencies installed."
echo ""

# -------------------------------------------------------------------
# 4. .env file
# -------------------------------------------------------------------
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo ".env created from .env.example."
    echo ""
    echo "  ACTION REQUIRED: Open .env and add your ANTHROPIC_API_KEY."
    echo "  The app will start without it, but AI vibe matching will be disabled."
  else
    echo "WARNING: .env.example not found. Create .env manually."
  fi
else
  echo ".env already exists. Skipping copy."
fi

echo ""

# -------------------------------------------------------------------
# 5. Smoke test — import backend without errors
# -------------------------------------------------------------------
echo "Running import smoke test..."
$PYTHON -c "
import sys
sys.path.insert(0, '.')
try:
    import backend.main
    print('Backend import OK.')
except Exception as e:
    print(f'Backend import FAILED: {e}')
    sys.exit(1)
"

echo ""
echo "======================================"
echo "  Setup complete!"
echo "======================================"
echo ""
echo "  Start the server:"
echo "    python run.py"
echo ""
echo "  Then open:"
echo "    http://localhost:8000/discovery.html"
echo "    http://localhost:8000/docs         (API explorer)"
echo ""
