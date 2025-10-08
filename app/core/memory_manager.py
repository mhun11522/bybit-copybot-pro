"""Memory management and cleanup utilities."""

import gc
import asyncio
import weakref
from typing import Dict, Set, Any, Optional
from app.core.logging import system_logger

class MemoryManager:
    """Memory management system for tracking and cleaning up resources."""
    
    def __init__(self):
        self._tracked_objects: Dict[str, weakref.WeakSet] = {}
        self._cleanup_callbacks: Dict[str, list] = {}
        self._memory_threshold = 100 * 1024 * 1024  # 100MB threshold
    
    def track_object(self, category: str, obj: Any, cleanup_callback: Optional[callable] = None):
        """Track an object for cleanup."""
        if category not in self._tracked_objects:
            self._tracked_objects[category] = weakref.WeakSet()
        
        self._tracked_objects[category].add(obj)
        
        if cleanup_callback:
            if category not in self._cleanup_callbacks:
                self._cleanup_callbacks[category] = []
            self._cleanup_callbacks[category].append(cleanup_callback)
    
    def cleanup_category(self, category: str) -> int:
        """Clean up all objects in a category."""
        cleaned_count = 0
        
        # Run cleanup callbacks
        if category in self._cleanup_callbacks:
            for callback in self._cleanup_callbacks[category]:
                try:
                    callback()
                    cleaned_count += 1
                except Exception as e:
                    system_logger.warning(f"Cleanup callback failed: {e}")
            self._cleanup_callbacks[category].clear()
        
        # Clear tracked objects
        if category in self._tracked_objects:
            cleaned_count += len(self._tracked_objects[category])
            self._tracked_objects[category].clear()
        
        return cleaned_count
    
    def cleanup_all(self) -> Dict[str, int]:
        """Clean up all tracked objects."""
        results = {}
        for category in list(self._tracked_objects.keys()):
            results[category] = self.cleanup_category(category)
        
        # Force garbage collection
        collected = gc.collect()
        system_logger.info(f"Memory cleanup completed, {collected} objects collected")
        
        return results
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size
            'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            'percent': process.memory_percent(),
            'tracked_categories': list(self._tracked_objects.keys()),
            'total_tracked_objects': sum(len(objs) for objs in self._tracked_objects.values())
        }
    
    def check_memory_threshold(self) -> bool:
        """Check if memory usage exceeds threshold."""
        stats = self.get_memory_stats()
        return stats['rss_mb'] > (self._memory_threshold / 1024 / 1024)
    
    async def periodic_cleanup(self, interval: int = 300):
        """Periodic memory cleanup task."""
        while True:
            await asyncio.sleep(interval)
            
            if self.check_memory_threshold():
                system_logger.warning("Memory threshold exceeded, performing cleanup")
                results = self.cleanup_all()
                system_logger.info(f"Cleanup results: {results}")
            else:
                # Light cleanup
                gc.collect()

# Global memory manager instance
_memory_manager = None

def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager

def track_resource(category: str, obj: Any, cleanup_callback: Optional[callable] = None):
    """Track a resource for cleanup."""
    manager = get_memory_manager()
    manager.track_object(category, obj, cleanup_callback)

async def cleanup_resources():
    """Clean up all tracked resources."""
    manager = get_memory_manager()
    return manager.cleanup_all()

def get_memory_stats() -> Dict[str, Any]:
    """Get current memory statistics."""
    manager = get_memory_manager()
    return manager.get_memory_stats()
