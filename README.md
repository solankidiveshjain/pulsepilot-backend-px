# PulsePilot Backend API

AI-powered social media comment management backend built with FastAPI, Supabase, and LangChain.

## 🚀 Features

- **Multi-platform Social Media Integration** - Instagram, Twitter, YouTube, LinkedIn
- **AI-Powered Reply Suggestions** - Using GPT-4 Turbo and LangChain
- **Vector Similarity Search** - pgvector for finding similar comments
- **Real-time Webhook Processing** - Async comment ingestion
- **Sentiment & Emotion Classification** - AI-powered comment analysis
- **Token Usage Tracking** - Complete billing and quota management
- **Team Management** - Multi-tenant architecture with Supabase Auth

## 🛠 Tech Stack

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL with pgvector (Supabase)
- **ORM**: SQLModel
- **Authentication**: Supabase Auth with JWT
- **AI/ML**: LangChain, OpenAI GPT-4, sentence-transformers
- **Background Tasks**: ARQ with Redis
- **Monitoring**: Prometheus metrics
- **Deployment**: Docker, Vercel

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension
- Redis (for background tasks)
- Supabase project
- OpenAI API key
- Social media API credentials

## 🔧 Installation

1. **Clone the repository**
   \`\`\`bash
   git clone <repository-url>
   cd pulsepilot-backend
   \`\`\`

2. **Install dependencies**
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

3. **Set up environment variables**
   \`\`\`bash
   cp .env.example .env
   # Edit .env with your configuration
   \`\`\`

4. **Initialize the database**
   \`\`\`bash
   python scripts/init_db.py
   \`\`\`

5. **Run the application**
   \`\`\`bash
   uvicorn main:app --reload
   \`\`\`

## 🌐 Environment Variables

### Required Variables

\`\`\`env
# Supabase (automatically provided by Vercel integration)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
POSTGRES_URL=postgresql://...
POSTGRES_URL_NON_POOLING=postgresql://...

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Social Media APIs
INSTAGRAM_APP_ID=your-instagram-app-id
INSTAGRAM_APP_SECRET=your-instagram-app-secret
TWITTER_CONSUMER_KEY=your-twitter-consumer-key
TWITTER_CONSUMER_SECRET=your-twitter-consumer-secret
YOUTUBE_CLIENT_ID=your-youtube-client-id
YOUTUBE_CLIENT_SECRET=your-youtube-client-secret
LINKEDIN_CLIENT_ID=your-linkedin-client-id
LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret

# Redis
REDIS_URL=redis://localhost:6379
\`\`\`

## 🚀 Deployment

### Vercel Deployment

1. **Connect to Vercel**
   \`\`\`bash
   vercel
   \`\`\`

2. **Set environment variables in Vercel dashboard**

3. **Deploy**
   \`\`\`bash
   vercel --prod
   \`\`\`

### Docker Deployment

1. **Build the image**
   \`\`\`bash
   docker build -t pulsepilot-backend .
   \`\`\`

2. **Run the container**
   \`\`\`bash
   docker run -p 8000:8000 --env-file .env pulsepilot-backend
   \`\`\`

## 📚 API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Key Endpoints

- `POST /teams/{teamId}/platforms/{platform}/connections` - Connect social media account
- `GET /teams/{teamId}/comments/{commentId}/suggestions` - Get AI reply suggestions
- `POST /teams/{teamId}/comments/{commentId}/reply` - Submit reply
- `POST /webhooks/{platform}` - Webhook for comment ingestion
- `POST /api/embeddings/generate` - Generate comment embeddings
- `POST /api/classify` - Classify comment sentiment/emotion

## 🔄 Background Tasks

The system uses ARQ for background processing:

- **Comment Processing**: Embedding generation and classification
- **Reply Submission**: Async posting to social platforms
- **Batch Operations**: Bulk processing for performance

## 📊 Monitoring

- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics` (Prometheus format)
- **Logs**: Structured JSON logging

## 🧪 Testing

\`\`\`bash
# Run tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_api.py
\`\`\`

## 🔒 Security

- JWT authentication with Supabase
- Webhook signature verification
- Role-based access control
- Input validation with Pydantic
- SQL injection protection with SQLModel

## 📈 Performance

- Async/await throughout
- Connection pooling
- Background task processing
- Vector similarity search optimization
- Proper database indexing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.
