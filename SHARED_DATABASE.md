# Shared Database Configuration Guide

## Overview

OCRMill supports shared database configuration for multi-user environments, compatible with TariffMill's database sharing approach. This allows multiple users across different platforms (Windows and Linux) to access the same parts database.

## Features

- **Platform-Specific Paths**: Configure separate database paths for Windows and Linux
- **Cross-Platform Compatibility**: Same config.json works on both Windows and Linux
- **TariffMill Integration**: Share the same database with TariffMill
- **Automatic Backups**: Configure automatic database backups to protect your data

## Configuration

### Using the Settings Dialog

1. Open **Settings** (gear icon in toolbar or Ctrl+,)
2. Navigate to **Database** in the sidebar
3. Configure **Shared Database (Multi-User)** section:
   - **Linux Path**: Path to database on Linux/macOS (e.g., `/home/shared/parts_database.db`)
   - **Windows Path**: Path to database on Windows (e.g., `\\server\share\parts_database.db` or `Z:\shared\parts_database.db`)
4. Click **Apply Platform Paths** to enable shared database
5. Restart the application to use the new database

### Using config.json

You can manually edit `config.json` to configure shared database:

```json
{
  "database_type": "shared",
  "database_path": "Z:/Shared/TariffMill/parts_database.db",
  "windows_database_path": "Z:/Shared/TariffMill/parts_database.db",
  "linux_database_path": "/mnt/shared/TariffMill/parts_database.db"
}
```

## Platform Detection

OCRMill automatically selects the correct database path based on the platform:

| Platform | Path Used |
|----------|-----------|
| Windows | `windows_database_path` |
| Linux | `linux_database_path` |
| macOS | `linux_database_path` |

This allows the same `config.json` to work across all platforms.

## Database Types

### Local Database

- **Location**: `Resources/parts_database.db` (relative to application)
- **Use Case**: Single-user, standalone installation
- **Benefits**: No network dependencies, fastest performance

**To switch to local database:**
1. Open Settings → Database
2. Click **Use Local Database**
3. Restart application

### Shared Database

- **Location**: Network share or shared folder
- **Use Case**: Multi-user environments, TariffMill integration
- **Benefits**: Centralized data, shared parts master

**To switch to shared database:**
1. Configure platform-specific paths in Settings → Database
2. Click **Apply Platform Paths**
3. Restart application

## Network Share Best Practices

### Windows Network Shares

**UNC Paths** (recommended for servers):
```
\\server\share\parts_database.db
\\192.168.1.10\TariffMill\parts_database.db
```

**Mapped Drives** (recommended for simplicity):
```
Z:\Shared\TariffMill\parts_database.db
Y:\Database\parts_database.db
```

### Linux/macOS Network Shares

**NFS Mounts**:
```
/mnt/shared/parts_database.db
/home/shared/TariffMill/parts_database.db
```

**SMB/CIFS Mounts**:
```
/mnt/smb/TariffMill/parts_database.db
```

## Important Notes

### SQLite on Network Shares

⚠️ **Concurrent Access Warning**: SQLite on network shares works best for **sequential access**. Avoid having multiple users edit the same record simultaneously.

**Best Practices**:
- ✅ Multiple users reading data (no issues)
- ✅ Users editing different parts (safe)
- ⚠️ Multiple users editing the same part (potential conflicts)
- ❌ High-concurrency write operations (not recommended)

### Database Schema Compatibility

OCRMill v0.99.16+ uses TariffMill's database schema:
- Table: `parts_master` (not `parts`)
- Columns: `steel_ratio`, `aluminum_ratio`, `non_steel_ratio`

See [SCHEMA_MIGRATION.md](SCHEMA_MIGRATION.md) for migration details.

## Database Backups

### Automatic Backups

Configure automatic backups in Settings → Database:

1. Set **Backup Folder** location
2. Enable **Enable automatic backups** checkbox
3. Save settings

**Backup Schedule**:
- Backups are created automatically before database operations
- Configurable retention policy (future feature)

### Manual Backups

To manually backup the database:

```bash
# Windows
copy Z:\Shared\parts_database.db C:\Backups\parts_database_backup.db

# Linux
cp /mnt/shared/parts_database.db ~/backups/parts_database_backup.db
```

## TariffMill Integration

### Shared Database with TariffMill

OCRMill and TariffMill can share the same database:

**config.json** (both applications):
```json
{
  "database_type": "shared",
  "windows_database_path": "Z:/Shared/TariffMill/parts_database.db",
  "linux_database_path": "/mnt/shared/TariffMill/parts_database.db",
  "shared_templates_folder": "Z:/Shared/TariffMill/Templates"
}
```

**Benefits**:
- ✅ Single source of truth for parts data
- ✅ Shared material composition data
- ✅ Shared invoice templates
- ✅ Consistent HTS codes and MIDs

### Shared Templates

In addition to sharing the database, you can share templates:

1. Set **shared_templates_folder** to TariffMill's template folder
2. Refresh templates in Settings → Templates
3. Templates from the shared folder appear with a network indicator

## Troubleshooting

### Database Not Found

**Error**: "Cannot access database at [path]"

**Solutions**:
- Verify network share is mounted/accessible
- Check path spelling and permissions
- Ensure database file exists at the specified location
- Try using **Use Local Database** temporarily

### Permission Denied

**Error**: "Permission denied when accessing [path]"

**Solutions**:
- Check file permissions on the network share
- Ensure your user has read/write access
- On Linux, verify mount options include `rw` (read-write)

### Database Locked

**Error**: "Database is locked"

**Causes**:
- Another user is writing to the database
- Previous crash left a lock file

**Solutions**:
- Wait a few seconds and retry
- Check for `.db-journal` or `.db-wal` files and remove if stale
- Contact other users to ensure they've closed the application

### Slow Performance

**Symptoms**: Database operations are slow

**Solutions**:
- Check network connection speed
- Consider using local database for better performance
- Close unnecessary database-heavy operations
- Verify network share is not overloaded

## Example Configurations

### Single Windows User

```json
{
  "database_type": "local",
  "database_path": "Resources/parts_database.db"
}
```

### Windows Team with Mapped Drive

```json
{
  "database_type": "shared",
  "database_path": "Z:/Shared/parts_database.db",
  "windows_database_path": "Z:/Shared/parts_database.db",
  "linux_database_path": "",
  "backup_folder": "C:/Users/username/Desktop/DB_Backups",
  "enable_automatic_backups": true
}
```

### Cross-Platform Team

```json
{
  "database_type": "shared",
  "database_path": "Z:/Shared/TariffMill/parts_database.db",
  "windows_database_path": "Z:/Shared/TariffMill/parts_database.db",
  "linux_database_path": "/mnt/tariffmill/parts_database.db",
  "shared_templates_folder": "Z:/Shared/TariffMill/Templates",
  "backup_folder": "~/backups/tariffmill",
  "enable_automatic_backups": true
}
```

### TariffMill Integration

```json
{
  "database_type": "shared",
  "database_path": "\\\\fileserver\\TariffMill\\parts_database.db",
  "windows_database_path": "\\\\fileserver\\TariffMill\\parts_database.db",
  "linux_database_path": "/mnt/smb/TariffMill/parts_database.db",
  "shared_templates_folder": "\\\\fileserver\\TariffMill\\Templates"
}
```

## Version History

- **v0.99.17** - Added shared database configuration with platform-specific paths
- **v0.99.16** - Schema migration to TariffMill compatibility
- **v0.99.15** - Initial database support

## Support

For issues or questions:
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [SCHEMA_MIGRATION.md](SCHEMA_MIGRATION.md)
- Report issues at https://github.com/ProcessLogicLabs/OCRMill/issues
