# Deploy Phase - Application Deployment

## Your Task
Prepare and optionally deploy the application to {{TARGET}}.

## Configuration
- **Target Platform:** {{TARGET}}
- **Auto Deploy:** {{AUTO_DEPLOY}}
- **Project Directory:** {{PROJECT_DIR}}

## Instructions

### 1. Analyze Project

First, understand what we're deploying:
- Detect the framework (Next.js, React, FastAPI, etc.)
- Identify the language runtime (Node.js, Python, etc.)
- Check for existing deployment configuration
- Identify required environment variables
- Note any database or external service dependencies

### 2. Create Deployment Configuration

Based on the target platform:

---

#### Docker Deployment

Create a multi-stage `Dockerfile`:

```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Copy only production dependencies
COPY --from=builder /app/package*.json ./
RUN npm ci --only=production

# Copy built application
COPY --from=builder /app/dist ./dist

EXPOSE 3000
CMD ["node", "dist/index.js"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "${PORT:-3000}:3000"
    env_file:
      - .env
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:18-alpine
    environment:
      POSTGRES_DB: ${DB_NAME:-app}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

---

#### Vercel Deployment

Create `vercel.json`:
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": null,
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/$1" }
  ],
  "env": {
    "NODE_ENV": "production"
  }
}
```

---

#### Railway Deployment

Create `railway.json`:
```json
{
  "build": {
    "builder": "nixpacks"
  },
  "deploy": {
    "startCommand": "npm start",
    "healthcheckPath": "/health"
  }
}
```

Or `Procfile`:
```
web: npm start
```

---

### 3. Environment Variables

Create `.env.example` with all required variables:

```bash
# Application
NODE_ENV=production
PORT=3000

# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# Authentication
JWT_SECRET=change-me-in-production
SESSION_SECRET=change-me-in-production

# External Services
# API_KEY=your-api-key
```

### 4. Build & Test Locally

Verify the deployment configuration works:

**For Docker:**
```bash
docker build -t app .
docker run -p 3000:3000 --env-file .env app
# Test: curl http://localhost:3000/health
```

**For Node.js:**
```bash
npm run build
npm start
# Test: curl http://localhost:3000/health
```

### 5. Deploy (if auto_deploy is true)

Only execute deployment if `auto_deploy` is enabled:

**Docker to registry:**
```bash
docker tag app registry.example.com/app:latest
docker push registry.example.com/app:latest
```

**Vercel:**
```bash
npx vercel --prod
```

**Railway:**
```bash
railway up
```

### 6. Verify Deployment

After deployment:
- [ ] Application is accessible
- [ ] Health endpoint responds
- [ ] Database connection works
- [ ] All features function correctly
- [ ] No console errors

## Output Format

Save as `DEPLOYMENT.md`:

```markdown
# Deployment Guide

## Project Info
- **Framework:** [detected framework]
- **Runtime:** [Node.js/Python/etc]
- **Target:** {{TARGET}}

## Prerequisites

- [List required tools: Docker, Node.js, etc.]
- [List required accounts: Vercel, Railway, etc.]
- [List required CLI tools]

## Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| DATABASE_URL | PostgreSQL connection string | Yes | postgresql://... |
| JWT_SECRET | JWT signing secret | Yes | [random-string] |

## Local Development

```bash
# Install dependencies
npm install

# Set up environment
cp .env.example .env
# Edit .env with your values

# Start development server
npm run dev
```

## Build

```bash
# Build for production
npm run build

# Test the build locally
npm start
```

## Deploy to {{TARGET}}

### Using Docker

```bash
# Build the image
docker build -t my-app .

# Run locally to test
docker run -p 3000:3000 --env-file .env my-app

# Deploy to your container registry
docker tag my-app your-registry/my-app:latest
docker push your-registry/my-app:latest
```

### Using [Platform CLI]

```bash
# Deploy command
[platform-specific deploy command]
```

## Post-Deployment

1. **Verify Health:**
   ```bash
   curl https://your-app.example.com/health
   ```

2. **Check Logs:**
   ```bash
   [platform-specific log command]
   ```

3. **Monitor:**
   - Set up uptime monitoring
   - Configure error alerting
   - Set up log aggregation

## Rollback

If something goes wrong:

```bash
# Roll back to previous version
[rollback commands]
```

## URLs

- **Production:** [URL if deployed]
- **Staging:** [URL if applicable]
- **Health Check:** [URL]/health

## Troubleshooting

### Common Issues

**Issue: Application won't start**
- Check environment variables are set
- Verify database connection string
- Check logs for specific errors

**Issue: Database connection fails**
- Verify DATABASE_URL is correct
- Check network/firewall rules
- Ensure database server is running
```

## Security Reminders

- NEVER commit secrets to git
- Use environment variables for all sensitive data
- Rotate secrets after any exposure
- Use HTTPS in production
- Set secure headers (CSP, HSTS, etc.)
