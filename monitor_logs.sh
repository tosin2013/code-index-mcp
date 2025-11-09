#!/bin/bash
# Monitor Cloud Run logs for progress updates

echo "🔍 Monitoring Cloud Run logs for progress..."
echo "Press Ctrl+C to stop"
echo ""

gcloud run services logs tail code-index-mcp-dev \
    --region=us-east1 \
    --format="value(textPayload)" \
    | grep --line-buffered -E "\[INGESTION|INDEX PROGRESS|ERROR\]" \
    | while read -r line; do
        echo "$(date '+%H:%M:%S') | $line"
    done
