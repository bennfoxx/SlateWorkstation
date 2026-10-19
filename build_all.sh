#!/bin/zsh
# Builds both SuperJoy Slating Workstation and MSTR-SL8R apps and DMGs simultaneously.
# Usage: ./build_all.sh
set -e
cd "${0:A:h}"

echo "=========================================="
echo "1/2 Building SuperJoy Slating Workstation"
echo "=========================================="
./build_dmg.sh

echo ""
echo "=========================================="
echo "2/2 Building MSTR-SL8R"
echo "=========================================="
./build_mstr_sl8r_dmg.sh

echo ""
echo "=========================================="
echo "All builds completed successfully!"
echo "• SuperJoy_Slating_Workstation_v1.0.0.dmg"
echo "• MSTR_SL8R_v1.0.0.dmg"
echo "=========================================="
