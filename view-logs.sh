#!/bin/bash
# ============================================================================
# Smart iInvoice - Log Viewer (Linux/Mac)
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================================${NC}"
echo -e "${CYAN}           Smart iInvoice - Log Viewer${NC}"
echo -e "${CYAN}============================================================================${NC}"
echo ""

if [ ! -d "logs" ]; then
    echo -e "${YELLOW}No logs directory found. Run ./setup.sh or ./run.sh first.${NC}"
    exit 1
fi

LOG_COUNT=$(ls -1 logs/*.log 2>/dev/null | wc -l)
if [ "$LOG_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No log files found.${NC}"
    exit 1
fi

echo "Available log files:"
echo ""
ls -lht logs/*.log 2>/dev/null | head -10

echo ""
echo -e "${GREEN}Select log type to view:${NC}"
echo ""
echo "1. Latest setup log"
echo "2. Latest run log"
echo "3. Latest Django log"
echo "4. Latest Celery log"
echo "5. Latest Redis log"
echo "6. All logs (combined)"
echo "7. Tail latest Django log (live)"
echo "8. Exit"
echo ""

read -p "Enter choice (1-8): " CHOICE

case $CHOICE in
    1)
        LOGFILE=$(ls -t logs/setup_*.log 2>/dev/null | head -1)
        ;;
    2)
        LOGFILE=$(ls -t logs/run_*.log 2>/dev/null | head -1)
        ;;
    3)
        LOGFILE=$(ls -t logs/django_*.log 2>/dev/null | head -1)
        ;;
    4)
        LOGFILE=$(ls -t logs/celery_*.log 2>/dev/null | head -1)
        ;;
    5)
        LOGFILE=$(ls -t logs/redis_*.log 2>/dev/null | head -1)
        ;;
    6)
        echo ""
        echo -e "${CYAN}Showing all logs (most recent first):${NC}"
        echo ""
        for log in $(ls -t logs/*.log); do
            echo -e "${GREEN}=== $(basename $log) ===${NC}"
            cat "$log"
            echo ""
        done
        exit 0
        ;;
    7)
        LOGFILE=$(ls -t logs/django_*.log 2>/dev/null | head -1)
        if [ -z "$LOGFILE" ]; then
            echo -e "${YELLOW}No Django log file found.${NC}"
            exit 1
        fi
        echo ""
        echo -e "${CYAN}Tailing: $LOGFILE${NC}"
        echo -e "${YELLOW}Press Ctrl+C to exit${NC}"
        echo ""
        tail -f "$LOGFILE"
        exit 0
        ;;
    8)
        exit 0
        ;;
    *)
        echo "Invalid choice."
        exit 1
        ;;
esac

if [ -z "$LOGFILE" ]; then
    echo -e "${YELLOW}No log file found for this type.${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}Viewing: $LOGFILE${NC}"
echo ""
cat "$LOGFILE"
echo ""
