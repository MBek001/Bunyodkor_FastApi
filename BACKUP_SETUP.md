# Automatic Backup to Telegram - Setup Guide

This guide explains how to configure automatic database backups to a Telegram channel.

## Prerequisites

1. **Telegram Bot**: You need to create a Telegram bot and get its token
2. **Telegram Channel/Chat**: A channel or chat where backups will be sent
3. **PostgreSQL**: The system uses `pg_dump` utility (ensure it's installed)

## Step 1: Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the **bot token** (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

## Step 2: Get Your Chat ID

### For a Private Chat:
1. Send a message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Look for `"chat":{"id":123456789}` in the response
4. Copy the chat ID

### For a Channel:
1. Add your bot to the channel as an administrator
2. Post a message in the channel
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Look for the channel ID (format: `-100123456789`)

## Step 3: Configure Environment Variables

Add the following to your `.env` file:

```env
# Telegram Backup Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-100123456789
BACKUP_ENABLED=true
BACKUP_HOUR=3  # Hour of day to run backup (0-23, default is 3 AM)
```

## Step 4: Install Dependencies

Make sure all required packages are installed:

```bash
pip install -r requirements.txt
```

## Step 5: Verify Configuration

You can verify your backup configuration using the API:

```bash
# Get backup status
curl -X GET "http://localhost:8008/backup/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Manual Backup

To trigger a manual backup (super admin only):

```bash
curl -X POST "http://localhost:8008/backup/manual" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## How It Works

1. **Automatic Backups**: The system automatically creates a database backup every 24 hours at the configured hour
2. **Compression**: Backups are compressed using gzip to reduce file size
3. **Telegram Upload**: Compressed backups are sent to your Telegram channel/chat
4. **Cleanup**: Old backups are automatically cleaned up (keeps last 7 backups)
5. **File Size Limit**: Telegram bots can only send files up to 50 MB

## Backup File Format

Backup files are named: `bunyodkor_backup_YYYYMMDD_HHMMSS.sql.gz`

Example: `bunyodkor_backup_20251203_030000.sql.gz`

## Restoring from Backup

To restore a database from a backup file:

```bash
# 1. Decompress the backup
gunzip bunyodkor_backup_20251203_030000.sql.gz

# 2. Restore to PostgreSQL
psql -h localhost -U your_user -d your_database < bunyodkor_backup_20251203_030000.sql
```

## Troubleshooting

### Backups Not Being Sent

1. Check that `BACKUP_ENABLED=true` in your `.env` file
2. Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct
3. Ensure the bot has permission to send messages to the chat/channel
4. Check application logs for error messages

### File Size Too Large

If your database backup exceeds 50 MB:

1. The system will create the backup locally but won't send it to Telegram
2. You'll receive a notification about the size limit
3. Consider:
   - Using database partitioning
   - Archiving old data
   - Using an alternative backup storage solution

### pg_dump Not Found

Ensure PostgreSQL client tools are installed:

```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# macOS
brew install postgresql
```

## Security Considerations

1. **Keep your bot token secret** - Never commit it to version control
2. **Use environment variables** - Store sensitive data in `.env` file
3. **Restrict bot permissions** - Only give necessary permissions to the bot
4. **Secure your channel** - Make the backup channel private
5. **Regular testing** - Test backup restoration periodically

## API Endpoints

### POST /backup/manual
Trigger a manual backup (super admin only)

**Response:**
```json
{
  "data": {
    "message": "Manual backup completed successfully",
    "telegram_configured": true
  }
}
```

### GET /backup/status
Get backup configuration status (super admin only)

**Response:**
```json
{
  "data": {
    "backup_enabled": true,
    "backup_hour": 3,
    "telegram_configured": true,
    "telegram_chat_id": "-100123456789"
  }
}
```

## Logs

Backup operations are logged with timestamps. Check application logs for:

- Backup creation status
- File size information
- Telegram upload status
- Error messages

Example log output:
```
2025-12-03 03:00:00 - app.services.backup - INFO - Starting automated database backup...
2025-12-03 03:00:05 - app.services.backup - INFO - Creating database backup: bunyodkor_backup_20251203_030000.sql
2025-12-03 03:00:15 - app.services.backup - INFO - Compressing backup: bunyodkor_backup_20251203_030000.sql.gz
2025-12-03 03:00:20 - app.services.backup - INFO - Backup created successfully: (15.43 MB)
2025-12-03 03:00:25 - app.services.backup - INFO - Sending backup to Telegram chat: -100123456789
2025-12-03 03:00:30 - app.services.backup - INFO - Backup sent to Telegram successfully
2025-12-03 03:00:31 - app.services.backup - INFO - Backup routine completed successfully
```
