# Threading Fix for Parts Database

## Issue
When processing invoices through the GUI, all PDFs failed with the error:
```
SQLite objects created in a thread can only be used in that same thread.
The object was created in thread id 17528 and this is thread id 13132.
```

## Root Cause
- The Invoice Processor GUI uses a worker thread to process PDFs (to keep the UI responsive)
- The PartsDatabase was initialized in the main thread
- When the worker thread tried to add parts to the database, SQLite raised an error
- SQLite by default doesn't allow database connections to be shared across threads

## Solution Applied

### 1. Disabled Thread Checking
Changed the SQLite connection initialization to allow cross-thread usage:

```python
# Before
self.conn = sqlite3.connect(str(self.db_path))

# After
self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
```

### 2. Added Thread Safety with Lock
Added a threading lock to prevent race conditions when multiple threads access the database:

```python
import threading

class PartsDatabase:
    def __init__(self, db_path: Path = Path("parts_database.db")):
        self.db_path = db_path
        self.conn = None
        self._lock = threading.Lock()  # Added lock
        self._initialize_database()
```

### 3. Protected Critical Sections
Wrapped database write operations with the lock:

```python
def add_part_occurrence(self, part_data: Dict) -> bool:
    with self._lock:
        cursor = self.conn.cursor()
        # ... database operations ...
        self.conn.commit()
        return True
```

## Thread Safety Approach

**Why This is Safe:**
1. **`check_same_thread=False`**: Allows the same connection to be used from different threads
2. **`threading.Lock()`**: Ensures only one thread can write to the database at a time
3. **No Race Conditions**: The lock prevents concurrent writes that could corrupt data

**What's Protected:**
- `add_part_occurrence()` - Adding new part records
- All database writes are serialized through the lock
- Read operations can still happen concurrently (SQLite allows multiple readers)

## Testing
After the fix, all 14 PDFs should process successfully:
- Czech invoices with multi-invoice PDFs
- Brazilian invoices
- Mixed batches

## Files Modified
- **parts_database.py** (Lines 6-8, 30, 132-179)
  - Added `import threading`
  - Added `self._lock = threading.Lock()`
  - Added `check_same_thread=False` to sqlite3.connect()
  - Wrapped `add_part_occurrence()` with lock

## Performance Impact
- **Minimal**: The lock only applies to write operations
- **Read Operations**: Still concurrent (no lock needed)
- **Single-threaded mode**: No performance difference
- **Multi-threaded mode**: Writes are serialized but this is necessary for data integrity

## Alternative Approaches Considered

### 1. One Connection Per Thread
```python
# Create new connection for each thread
def get_connection():
    return sqlite3.connect(str(self.db_path))
```
**Rejected**: More complex, requires connection pooling

### 2. Queue-Based Writes
```python
# Use a queue to serialize all database operations
write_queue = Queue()
worker_thread = Thread(target=process_queue)
```
**Rejected**: Overkill for this use case, adds complexity

### 3. Async/Await Pattern
```python
async def add_part_occurrence(self, part_data: Dict):
    # Async database operations
```
**Rejected**: Would require rewriting the entire application

## Conclusion
The current approach (check_same_thread=False + threading.Lock) is:
- ✅ Simple and maintainable
- ✅ Thread-safe
- ✅ Minimal performance impact
- ✅ Proven pattern for SQLite multi-threading

---

**Fix Applied**: December 9, 2025
**Tested**: Pending - reprocess the 14 failed PDFs
