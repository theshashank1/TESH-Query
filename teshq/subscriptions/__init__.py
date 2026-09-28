"""
TESHQ Subscriptions Package

Handles subscription management including subscribe/unsubscribe operations
with the TESHQ public API.

Note: Both subscribe and unsubscribe functionality are CLI-only and not
exposed as part of the public package API. Use the CLI commands instead:
    - teshq subscribe
    - teshq unsubscribe

This module contains internal subscription client implementations. Direct
usage of SubscriberClient or subscription models is not recommended.
"""

# No public exports - all subscription functionality is CLI-only
# Use: teshq subscribe / teshq unsubscribe commands

__all__: list[str] = []
