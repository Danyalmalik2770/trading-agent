#!/bin/bash
# Start the Trading Agents learner in the background (brain continues
# from brain.json — nothing learned is lost on restart).
cd "$(dirname "$0")" || exit 1
nohup python3 -u main.py learn >> learn.log 2>&1 &
echo $! > learner.pid
echo "learner started, pid $(cat learner.pid)"
