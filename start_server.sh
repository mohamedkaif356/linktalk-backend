#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   RAG Backend API - Server Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ .env file not found. Creating default .env...${NC}"
    cat > .env << EOF
DATABASE_URL=sqlite:///./rag_backend.db
DEVICE_FINGERPRINT_SALT=test-salt-change-in-production-$(date +%s)
ENVIRONMENT=development
EOF
    echo -e "${GREEN}✓ .env file created${NC}"
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi
echo ""

# Check if database exists, if not initialize it
if [ ! -f rag_backend.db ]; then
    echo -e "${YELLOW}⚠ Database not found. Initializing...${NC}"
    python3 -m app.db.init_db 2>&1 | grep -v "INFO sqlalchemy" || true
    if [ $? -eq 0 ] || [ -f rag_backend.db ]; then
        echo -e "${GREEN}✓ Database initialized${NC}"
    else
        echo -e "${RED}✗ Database initialization failed${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Database exists${NC}"
fi
echo ""

# Check if dependencies are installed
echo -e "${BLUE}Checking dependencies...${NC}"
python3 -c "import fastapi, uvicorn, sqlalchemy, pydantic" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠ Dependencies not installed. Installing...${NC}"
    python3 -m pip install -q -r requirements.txt 2>&1 | grep -v "WARNING" || true
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Dependencies installed${NC}"
    else
        echo -e "${RED}✗ Failed to install dependencies${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi
echo ""

# Display server information
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Server Information${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Server URL:${NC}     http://localhost:8000"
echo -e "${GREEN}API Base:${NC}       http://localhost:8000/api/v1"
echo -e "${GREEN}Swagger UI:${NC}     http://localhost:8000/docs"
echo -e "${GREEN}ReDoc:${NC}          http://localhost:8000/redoc"
echo -e "${GREEN}Health Check:${NC}   http://localhost:8000/health"
echo ""

# Display available endpoints
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Available Endpoints${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}POST${NC}   /api/v1/register-device"
echo -e "        Register a device and get authentication token"
echo ""
echo -e "${GREEN}GET${NC}    /health"
echo -e "        Health check endpoint"
echo ""
echo -e "${GREEN}GET${NC}    /"
echo -e "        Root endpoint"
echo ""

# Display database info
if [ -f rag_backend.db ]; then
    DB_SIZE=$(ls -lh rag_backend.db | awk '{print $5}')
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   Database Information${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}Database:${NC}    rag_backend.db"
    echo -e "${GREEN}Size:${NC}        $DB_SIZE"
    echo ""
fi

# Start the server
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Starting Server...${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""
echo ""

# Run uvicorn
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
