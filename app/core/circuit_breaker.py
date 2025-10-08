"""Circuit breaker for handling repeated API errors."""

import time
from typing import Dict, Any, Optional
from enum import Enum
from app.core.logging import system_logger

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Circuit is open, requests fail fast
    HALF_OPEN = "HALF_OPEN"  # Testing if service is back

class CircuitBreaker:
    """Circuit breaker for API calls to prevent cascading failures."""
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before trying again
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        """Record successful execution."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        
    def record_failure(self, exception: Exception):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        # Check if we should open the circuit
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            system_logger.warning(f"Circuit breaker opened after {self.failure_count} failures", {
                'failure_count': self.failure_count,
                'threshold': self.failure_threshold,
                'last_error': str(exception)
            })
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'last_failure_time': self.last_failure_time,
            'can_execute': self.can_execute()
        }

# Global circuit breaker instances
_bybit_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

def get_bybit_circuit_breaker() -> CircuitBreaker:
    """Get the global Bybit circuit breaker."""
    return _bybit_circuit_breaker

async def execute_with_circuit_breaker(circuit_breaker: CircuitBreaker, operation):
    """Execute operation with circuit breaker protection."""
    if not circuit_breaker.can_execute():
        raise Exception(f"Circuit breaker is {circuit_breaker.state.value}")
    
    try:
        result = await operation()
        circuit_breaker.record_success()
        return result
    except circuit_breaker.expected_exception as e:
        circuit_breaker.record_failure(e)
        raise
