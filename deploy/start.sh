#!/bin/bash
# Uruchamia trading system w screen jeśli nie działa
cd /home/claude-runner/ai-trading-system

if screen -ls | grep -q "trading"; then
    echo "Trading system już działa."
    exit 0
fi

screen -dmS trading /home/claude-runner/ai-trading-system/.venv/bin/python main.py
echo "Trading system uruchomiony."
