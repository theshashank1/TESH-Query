"""
TESHQ Subscriptions Package

Handles subscription management including subscribe/unsubscribe operations
with the TESHQ public API.

Exports:
    - SubscriberClient: Main client for API communication
    - SubscriptionRequest/UnsubscribeRequest: Pydantic request models
    - SubscriptionResponse/UnsubscribeResponse: Pydantic response models
    - SubscriptionResult/UnsubscribeResult: Result wrapper models
    - SubscriptionStatus/UnsubscribeStatus: Status enumerations
    - subscribe_user/unsubscribe_user: Convenience helper functions
"""

from teshq.subscriptions.client import (
    OSType,
    SubscriberClient,
    SubscriptionRequest,
    SubscriptionResponse,
    SubscriptionResult,
    SubscriptionStatus,
    UnsubscribeRequest,
    UnsubscribeResponse,
    UnsubscribeResult,
    UnsubscribeStatus,
    subscribe_user,
    unsubscribe_user,
)

__all__ = [
    "OSType",
    "SubscriberClient",
    "SubscriptionRequest",
    "SubscriptionResponse",
    "SubscriptionResult",
    "SubscriptionStatus",
    "UnsubscribeRequest",
    "UnsubscribeResponse",
    "UnsubscribeResult",
    "UnsubscribeStatus",
    "subscribe_user",
    "unsubscribe_user",
]
