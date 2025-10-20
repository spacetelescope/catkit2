#!/usr/bin/env python3
"""
Example: How to handle service crashes with the new crash detection

This example shows best practices for handling remote service failures.
"""

import logging
import time
import pytest
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RobustRemoteDataSubscriber:
    """
    A robust subscriber that handles remote service failures.
    
    Features:
    - Detects when remote service crashes
    - Automatic reconnection with exponential backoff
    - Graceful degradation
    - Detailed logging for debugging
    """
    
    def __init__(self, topic: str, max_retries: int = 5):
        """Initialize subscriber."""
        self.topic = topic
        self.max_retries = max_retries
        self.reconnect_delay = 1.0  # seconds
        self.max_reconnect_delay = 60.0  # seconds
        self.retry_count = 0
        self.message_count = 0
        self.error_count = 0
    
    def connect_to_broker(self, broker, message_subscription_mode=None):
        """Connect to message broker topic."""
        logger.info(f"Connecting to topic: {self.topic}")
        
        try:
            if message_subscription_mode is not None:
                subscription = broker.subscribe(
                    self.topic,
                    mode=message_subscription_mode
                )
            else:
                subscription = broker.subscribe(self.topic)
            logger.info(f"✓ Connected to topic: {self.topic}")
            return subscription
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return None
    
    def run_with_reconnect(self, broker):
        """
        Run subscriber with automatic reconnection on failure.
        """
        subscription = None
        
        while True:
            try:
                # Try to connect if not connected
                if subscription is None:
                    subscription = self.connect_to_broker(broker)
                    if subscription is None:
                        self._handle_connection_failure()
                        continue
                    self.retry_count = 0  # Reset retry count on successful connect
                
                # Get next message with timeout
                try:
                    message = subscription.get_next_message(
                        timeout_in_sec=5.0
                    )
                    
                    # Process message
                    self._process_message(message)
                    self.message_count += 1
                    
                    # Reset reconnect delay after successful message
                    self.reconnect_delay = 1.0
                    
                except RuntimeError as e:
                    error_msg = str(e).lower()
                    
                    if "appears to be inactive" in error_msg:
                        # Service crash detected!
                        logger.error(
                            f"✗ Remote service crashed: {e}"
                        )
                        self.error_count += 1
                        subscription = None  # Force reconnect
                        self._handle_service_crash()
                    else:
                        # Some other error
                        logger.error(f"Subscription error: {e}")
                        subscription = None
                        self._handle_subscription_error()
                
                except KeyboardInterrupt:
                    logger.info("Received interrupt, shutting down...")
                    break
                
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    subscription = None
                    self._handle_unexpected_error(e)
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Fatal error in main loop: {e}")
                break
        
        self._log_summary()
    
    def _process_message(self, message):
        """Process received message."""
        # Log every 100 messages
        if self.message_count % 100 == 0:
            logger.info(
                f"Received {self.message_count} messages "
                f"(frame_id={message.frame_id})"
            )
        
        # TODO: Add your actual message processing here
        # Example:
        # data = np.frombuffer(message.payload, dtype=...)
        # self.process_image(data)
    
    def _handle_connection_failure(self):
        """Handle failure to connect to broker."""
        logger.warning(
            f"Connection failed. "
            f"Retry {self.retry_count + 1}/{self.max_retries}"
        )
        
        self.retry_count += 1
        if self.retry_count >= self.max_retries:
            logger.error(
                f"Max connection retries ({self.max_retries}) exceeded. "
                f"Giving up."
            )
            raise RuntimeError("Failed to connect after max retries")
        
        # Wait before retrying
        logger.info(f"Waiting {self.reconnect_delay}s before retry...")
        time.sleep(self.reconnect_delay)
        
        # Exponential backoff
        self.reconnect_delay = min(
            self.reconnect_delay * 2,
            self.max_reconnect_delay
        )
    
    def _handle_service_crash(self):
        """Handle remote service crash."""
        logger.error("=" * 70)
        logger.error("REMOTE SERVICE CRASH DETECTED")
        logger.error("=" * 70)
        logger.error(f"Topic: {self.topic}")
        logger.error(f"Messages received: {self.message_count}")
        logger.error(f"Total errors: {self.error_count}")
        logger.error("=" * 70)
        
        # Strategies for recovery:
        # 1. Wait and retry (implemented below)
        # 2. Connect to backup service (add your logic)
        # 3. Use last known good state (add your logic)
        # 4. Alert operator (add your logic)
        
        logger.info("Attempting to reconnect in 10 seconds...")
        time.sleep(10)
    
    def _handle_subscription_error(self):
        """Handle subscription error (non-crash)."""
        logger.warning("Subscription error, attempting reconnect...")
        time.sleep(2)
    
    def _handle_unexpected_error(self, error):
        """Handle unexpected error."""
        logger.error(f"Unexpected error: {error}")
        logger.info("Waiting 5 seconds before retry...")
        time.sleep(5)
    
    def _log_summary(self):
        """Log final statistics."""
        logger.info("=" * 70)
        logger.info("SUBSCRIBER SHUTDOWN")
        logger.info("=" * 70)
        logger.info(f"Topic: {self.topic}")
        logger.info(f"Total messages received: {self.message_count}")
        logger.info(f"Total errors: {self.error_count}")
        logger.info(f"Success rate: "
                   f"{(1 - self.error_count / max(1, self.message_count + self.error_count)) * 100:.1f}%")
        logger.info("=" * 70)


def test_simple_exception_handling():
    """Simple example: just handle exceptions."""
    from catkit2.catkit_bindings import LocalMemory, LocalMessageBroker
    import numpy as np
    
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Simple Exception Handling")
    logger.info("=" * 70)
    
    # Create broker (normally loaded from testbed)
    header = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)
    broker = LocalMessageBroker.create(header, [block])
    
    topic = "camera/image/raw"
    
    # Publish test data
    test_data = np.arange(100, dtype=np.uint32)
    broker.publish_array(topic, test_data)
    logger.info(f"Published test message to {topic}")
    
    # Subscribe and try to receive
    subscription = broker.subscribe(topic)
    
    for attempt in range(3):
        try:
            logger.info(f"\nAttempt {attempt + 1}:")
            message = subscription.get_next_message(timeout_in_sec=1.0)
            
            if message:
                logger.info(
                    f"✓ Received message with frame_id={message.frame_id}"
                )
            else:
                logger.info("✗ No message received (timeout)")
        
        except RuntimeError as e:
            if "appears to be inactive" in str(e):
                logger.error(f"✗ Service is dead: {e}")
                break
            else:
                logger.info(f"✓ Got expected timeout: {e}")


def test_robust_subscriber_with_reconnection():
    """Robust example: with reconnection logic."""
    from catkit2.catkit_bindings import LocalMemory, LocalMessageBroker
    
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Robust Subscriber with Reconnection")
    logger.info("=" * 70)
    
    # Create broker
    header = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)
    broker = LocalMessageBroker.create(header, [block])
    
    topic = "camera/image/raw"
    
    # Create robust subscriber with limit to prevent infinite loop in tests
    subscriber = RobustRemoteDataSubscriber(topic, max_retries=1)
    
    # Override run_with_reconnect to add a max attempts limit for testing
    max_attempts = 3
    attempts = 0
    subscription = None
    
    while attempts < max_attempts:
        try:
            # Try to connect if not connected
            if subscription is None:
                subscription = subscriber.connect_to_broker(broker)
                if subscription is None:
                    attempts += 1
                    continue
                subscriber.retry_count = 0
            
            # Get next message with short timeout for testing
            try:
                message = subscription.get_next_message(
                    timeout_in_sec=1.0
                )
                subscriber._process_message(message)
                subscriber.message_count += 1
            except RuntimeError as e:
                error_msg = str(e).lower()
                
                if "appears to be inactive" in error_msg:
                    logger.error(f"Service crash detected: {e}")
                    subscriber.error_count += 1
                    subscription = None
                    attempts += 1
                else:
                    # Timeout is expected in test
                    attempts += 1
        
        except Exception as e:
            logger.error(f"Error in subscriber test: {e}")
            break
    
    subscriber._log_summary()
