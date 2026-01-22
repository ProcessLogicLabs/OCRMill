# Shared Database and Templates Configuration

## Overview

OCRMill and TariffMill can share the same parts database and templates for seamless integration. This guide explains how to configure both applications to work together.

## Shared Database Configuration

### 1. Choose a Shared Database Location

**Recommended Locations:**
- **Network Share** (multi-user): `Y:/Shared/Database/parts_database.db`
- **Local Shared** (single machine): `C:/ProgramData/ProcessLogicLabs/parts_database.db`
- **User Profile** (single machine, multi-user): `C:/Users/Shared/ProcessLogicLabs/parts_database.db`

### 2. Configure OCRMill

Edit `config.json`:
```json
{
  "database_path": "Y:/Shared/Database/parts_database.db",
  "shared_templates_folder": "Y:/Dev/Tariffmill/Templates"
}
```

### 3. Configure TariffMill

Edit `config.ini`:
```ini
[Database]
path = Y:/Shared/Database/parts_database.db

# OR use platform-specific paths for cross-platform setups:
windows_path = Y:/Shared/Database/parts_database.db
linux_path = /mnt/shared/Database/parts_database.db
```

## Shared Templates Configuration

### How It Works

1. **Template Priority:**
   - Local templates (in OCRMill/templates/) take priority
   - Shared templates (from TariffMill) are used as fallback

2. **Template Discovery:**
   - OCRMill automatically discovers templates from both locations
   - Templates with same name: local version is used
   - Templates only in shared folder: shared version is used

3. **Bidirectional Sync:**
   - Templates can be synced between OCRMill and TariffMill
   - Newer templates (by modification time) overwrite older ones
   - Templates unique to one location are copied to the other

### Configuration

**OCRMill config.json:**
```json
{
  "shared_templates_folder": "Y:/Dev/Tariffmill/Templates"
}
```

Set to `null` to disable shared templates:
```json
{
  "shared_templates_folder": null
}
```

## Benefits

✅ **Single Source of Truth** - All parts data in one database
✅ **Real-time Sync** - Updates immediately available in both apps
✅ **No Duplication** - Avoid data inconsistencies
✅ **Shared Templates** - Templates work in both applications
✅ **Automatic Fallback** - If shared path unavailable, uses local
✅ **Centralized Backups** - One database to backup

## Path Resolution

### Database Path

OCRMill's database path resolution (with fallback):

1. **Absolute Path:** `Y:/Shared/parts_database.db` → Used as-is
2. **Relative Path:** `Resources/parts_database.db` → Resolved to `<APP_PATH>/Resources/parts_database.db`
3. **Fallback:** If absolute path fails, falls back to `<APP_PATH>/Resources/parts_database.db`

### Templates Path

1. **Local:** `<APP_PATH>/templates/` (always checked first)
2. **Shared:** Path from `shared_templates_folder` config (checked second)
3. **Priority:** Local templates override shared templates with same name

## Example Configurations

### Scenario 1: Single Machine, Both Apps

```json
// OCRMill config.json
{
  "database_path": "C:/ProgramData/ProcessLogicLabs/parts_database.db",
  "shared_templates_folder": "C:/Dev/Tariffmill/Templates"
}
```

```ini
# TariffMill config.ini
[Database]
path = C:/ProgramData/ProcessLogicLabs/parts_database.db
```

### Scenario 2: Network Share (Multi-User)

```json
// OCRMill config.json
{
  "database_path": "Y:/ProcessLogic/Shared/parts_database.db",
  "shared_templates_folder": "Y:/ProcessLogic/Shared/Templates"
}
```

```ini
# TariffMill config.ini
[Database]
path = Y:/ProcessLogic/Shared/parts_database.db

[Templates]
shared_folder = Y:/ProcessLogic/Shared/Templates
```

### Scenario 3: Cross-Platform (Windows + Linux)

```json
// OCRMill config.json (Windows)
{
  "database_path": "Z:/shared/parts_database.db",
  "shared_templates_folder": "Z:/shared/templates"
}
```

```ini
# TariffMill config.ini
[Database]
windows_path = Z:/shared/parts_database.db
linux_path = /mnt/shared/parts_database.db
```

## Template Synchronization

### Auto-Sync on Startup

Templates are automatically discovered from both local and shared folders on startup.

### Manual Sync

Use the Templates tab in OCRMill to manually sync templates:
1. Go to Templates tab
2. Click "Sync Templates" button
3. Review sync results (to_shared, to_local, skipped, errors)

### Sync Behavior

- **Both exist:** Newer file (by modification time) wins
- **Only local:** Copied to shared folder
- **Only shared:** Copied to local folder
- **Conflicts:** Newer file overwrites older file

## Troubleshooting

### Database Path Issues

**Problem:** "Cannot access database path"
- **Solution:** Check network connectivity, folder permissions, and path spelling

**Problem:** "Database locked"
- **Solution:** Close other instances of OCRMill/TariffMill accessing the same database

### Template Loading Issues

**Problem:** Shared templates not appearing
- **Solution:** Check `shared_templates_folder` path in config.json
- Ensure path exists and contains .py template files
- Check Templates tab for template source (local vs shared)

**Problem:** Wrong template version being used
- **Solution:** Local templates always take priority
- Delete local version to force shared version to load
- Or sync templates to update local with shared version

## Best Practices

1. **Backup Regularly:** Schedule automatic backups of the shared database
2. **Test First:** Use a local copy for testing before changing shared database
3. **Network Stability:** Ensure stable network connection for shared paths
4. **Template Versioning:** Use template sync to keep versions in sync
5. **Permissions:** Ensure all users have read/write access to shared paths

## Security Considerations

- **Network Shares:** Use appropriate ACLs to restrict access
- **Database Encryption:** SQLite database files are not encrypted by default
- **Sensitive Data:** Consider using encrypted network shares for sensitive parts data

## Migration Guide

### Moving from Local to Shared Database

1. **Backup:** Create backup of local database
2. **Copy:** Copy local database to shared location
3. **Update Config:** Update both apps to point to shared path
4. **Test:** Verify both apps can access shared database
5. **Cleanup:** Keep local backup for 30 days before deleting

### Moving from Shared to Local Database

1. **Copy:** Copy shared database to local Resources folder
2. **Update Config:** Change database_path to relative path
3. **Test:** Verify local access works
4. **Note:** Other users will continue using shared database unless they also switch

## Version Compatibility

- **OCRMill:** v0.99.13+
- **TariffMill:** All versions with `config.ini` support
- **Database Schema:** Both apps must use compatible schema versions
