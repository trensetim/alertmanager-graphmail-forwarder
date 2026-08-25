# Deduplication inside the forwarder is unnecessary:
#    - Alertmanager dedups the notifications internally on the happy-path, sender-side
#    - Alertmanager HA deployments gossip to deduplicate across their entire cluster
#    - Alertmanager retries only when receiving a non-200 response
#    - An Alertmanager retry due to network failure (eg. timeout) is (upon proper configuration) a reasonably rare edge
#       case that we better not cover it: to force an appropriate timeout config on Alertmanager side And to save a lot of complexity
#    - If we dedup here, we would need to persist-across-restarts and gossip-across-replicas, which adds much complexity for a rare edge case
#    - Almost all other forwarder implementations do not have any dedup internally


# This file is only for documenting this design decision (and provide a git history anchor for the previous implementation).
