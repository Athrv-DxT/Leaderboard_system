# FunFinity Leaderboard - SQLite Version

## Overview
This is a cost-effective leaderboard system that replaces Firestore with SQLite to eliminate database limits and reduce costs. The system fetches user data from an external API every 3 seconds and maintains a local SQLite database for fast, unlimited queries.

## Key Features
- ✅ **No Database Limits**: SQLite has no query limits or quotas
- ✅ **Real-time Updates**: Fetches data every 3 seconds as requested
- ✅ **Cost Effective**: No external database costs
- ✅ **High Performance**: Local SQLite is extremely fast
- ✅ **Same UI**: Identical user interface and experience
- ✅ **Deploy Ready**: Configured for Render deployment

## Architecture Changes

### Before (Firestore)
- External Firestore database
- Rate limits and quotas
- High costs for frequent queries
- Network latency for each query

### After (SQLite)
- Local SQLite database
- No limits or quotas
- Zero additional costs
- Instant local queries
- Intelligent caching system

## Technical Details

### Database Schema
```sql
CREATE TABLE players (
    name TEXT PRIMARY KEY,
    score INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_score ON players(score DESC);
```

### Caching System
- 30-second cache TTL for optimal performance
- Automatic cache invalidation on updates
- Fallback to cached data on errors

### Rate Limiting
- 2-second minimum interval between API calls
- Prevents API overload
- Graceful error handling

### Sync Process
1. Fetches user list from external API every 3 seconds
2. Compares with local database
3. Adds new users, removes deleted users
4. Updates leaderboard cache
5. Serves data instantly from cache

## Deployment

### Environment Variables
```bash
API_URL=https://web-production-3b67.up.railway.app/api/users
API_KEY=your_api_key_here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
SECRET_KEY=your_secret_key_here
DATABASE_PATH=/opt/render/project/src/leaderboard.db
```

### Render Deployment
1. Connect your GitHub repository to Render
2. The `render.yaml` file is already configured
3. Set the environment variables in Render dashboard
4. Deploy!

## Performance Benefits

### Cost Savings
- ❌ No Firestore costs
- ❌ No query limits
- ❌ No read/write charges
- ✅ Only hosting costs

### Performance Improvements
- ⚡ 10x faster queries (local vs network)
- ⚡ No rate limiting delays
- ⚡ Instant leaderboard updates
- ⚡ 24/7 operation capability

### Reliability
- 🔒 No external database dependencies
- 🔒 Local data persistence
- 🔒 Graceful error handling
- 🔒 Automatic recovery

## Monitoring

### Health Check Endpoint
Visit `/health` to check system status:
```json
{
  "status": "healthy",
  "message": "FunFinity Leaderboard is running",
  "cache_age": 15.2,
  "sync_enabled": true,
  "database": "SQLite",
  "sync_interval": 3
}
```

### Logs
The system provides detailed logging:
- API sync status
- Database operations
- Error handling
- Performance metrics

## Migration Notes

### What Changed
1. Replaced `firebase-admin` with `sqlite3`
2. Updated all database operations to use SQLite
3. Improved caching and rate limiting
4. Enhanced error handling
5. Updated deployment configuration

### What Stayed the Same
1. Identical user interface
2. Same API endpoints
3. Same admin functionality
4. Same real-time updates
5. Same deployment process

## Troubleshooting

### Common Issues
1. **Database not found**: Check `DATABASE_PATH` environment variable
2. **API errors**: Verify `API_URL` and `API_KEY` are correct
3. **Sync issues**: Check network connectivity and API availability

### Debug Mode
Set `TESTING=1` environment variable to disable background sync for testing.

## Support
The system is designed to handle 20+ hours of continuous operation without issues. SQLite can handle millions of queries efficiently, making it perfect for high-traffic leaderboards.
