"""Performance monitoring and metrics collection."""

import time
import asyncio
from typing import Dict, Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field
from app.core.logging import system_logger

@dataclass
class PerformanceMetrics:
    """Performance metrics container."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = float('inf')
    error_rate: float = 0.0
    last_updated: float = field(default_factory=time.time)

class PerformanceMonitor:
    """Performance monitoring system."""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics: Dict[str, PerformanceMetrics] = defaultdict(PerformanceMetrics)
        self.response_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.start_time = time.time()
    
    def record_request(self, operation: str, response_time: float, success: bool = True):
        """Record a request with its response time and success status."""
        metrics = self.metrics[operation]
        metrics.total_requests += 1
        
        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1
            self.error_counts[operation] += 1
        
        # Update response time metrics
        self.response_times[operation].append(response_time)
        metrics.max_response_time = max(metrics.max_response_time, response_time)
        metrics.min_response_time = min(metrics.min_response_time, response_time)
        
        # Calculate average response time
        if self.response_times[operation]:
            metrics.average_response_time = sum(self.response_times[operation]) / len(self.response_times[operation])
        
        # Calculate error rate
        if metrics.total_requests > 0:
            metrics.error_rate = (metrics.failed_requests / metrics.total_requests) * 100
        
        metrics.last_updated = time.time()
    
    def get_metrics(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get performance metrics for an operation or all operations."""
        if operation:
            if operation not in self.metrics:
                return {}
            metrics = self.metrics[operation]
            return {
                'operation': operation,
                'total_requests': metrics.total_requests,
                'successful_requests': metrics.successful_requests,
                'failed_requests': metrics.failed_requests,
                'average_response_time': metrics.average_response_time,
                'max_response_time': metrics.max_response_time,
                'min_response_time': metrics.min_response_time if metrics.min_response_time != float('inf') else 0,
                'error_rate': metrics.error_rate,
                'last_updated': metrics.last_updated
            }
        else:
            return {op: self.get_metrics(op) for op in self.metrics.keys()}
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system performance metrics."""
        uptime = time.time() - self.start_time
        total_requests = sum(m.total_requests for m in self.metrics.values())
        total_errors = sum(m.failed_requests for m in self.metrics.values())
        overall_error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'uptime_seconds': uptime,
            'total_operations': len(self.metrics),
            'total_requests': total_requests,
            'total_errors': total_errors,
            'overall_error_rate': overall_error_rate,
            'operations': list(self.metrics.keys())
        }
    
    def log_performance_summary(self):
        """Log a performance summary."""
        system_metrics = self.get_system_metrics()
        system_logger.info("Performance Summary", {
            'uptime_hours': system_metrics['uptime_seconds'] / 3600,
            'total_requests': system_metrics['total_requests'],
            'total_errors': system_metrics['total_errors'],
            'overall_error_rate': system_metrics['overall_error_rate'],
            'operations': system_metrics['operations']
        })
        
        # Log top operations by request count
        sorted_ops = sorted(self.metrics.items(), key=lambda x: x[1].total_requests, reverse=True)
        for operation, metrics in sorted_ops[:5]:  # Top 5 operations
            system_logger.info(f"Operation: {operation}", {
                'total_requests': metrics.total_requests,
                'average_response_time': metrics.average_response_time,
                'error_rate': metrics.error_rate
            })

# Global performance monitor instance
_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor

def monitor_performance(operation: str):
    """Decorator to monitor function performance."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                response_time = time.time() - start_time
                monitor.record_request(operation, response_time, success)
        
        def sync_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                response_time = time.time() - start_time
                monitor.record_request(operation, response_time, success)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

async def log_performance_metrics():
    """Log performance metrics periodically."""
    monitor = get_performance_monitor()
    while True:
        await asyncio.sleep(300)  # Log every 5 minutes
        monitor.log_performance_summary()
