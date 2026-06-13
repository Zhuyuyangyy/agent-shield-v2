# AgentShield V2 Deployment Guide

## Prerequisites

- Python 3.9+
- pip package manager
- Docker (optional)

## Local Development Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd agent-shield-v2
```

### 2. Create Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=backend --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_database_shadow.py -v
```

### 5. Start Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Docker Deployment

### Build Image

```bash
docker build -t agent-shield-v2 .
```

### Run Container

```bash
docker run -p 8000:8000 agent-shield-v2
```

### Docker Compose

```bash
docker-compose up -d
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `info` | Logging level |

## Health Check

```bash
curl http://localhost:8000/health
# Response: {"status": "ok"}
```

## Production Considerations

### Security

- Use HTTPS in production
- Set appropriate CORS policies
- Use environment variables for sensitive configuration
- Enable rate limiting

### Monitoring

- Monitor audit logs for anomalies
- Track risk score distributions
- Alert on high block rates

### Scaling

- Use multiple worker processes
- Consider Redis for audit log storage
- Use database for persistent audit trails

## CI/CD Pipeline

The project uses GitHub Actions for CI/CD:

1. **Lint**: Runs ruff for code quality
2. **Test**: Runs pytest for unit and integration tests
3. **Build**: Builds Docker image (on main branch)

See `.github/workflows/ci.yml` for details.
